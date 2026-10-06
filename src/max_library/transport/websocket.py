"""
Low-level Async WebSocket Transport for MAX Protocol.
Handles connection lifecycle, heartbeat, auto-reconnect, and RPC dispatching (seq -> Future).
"""
import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

try:
    from websockets.asyncio.client import connect as ws_connect, ClientConnection
except ImportError:
    from websockets import connect as ws_connect  # type: ignore
    ClientConnection = Any  # type: ignore

from websockets.exceptions import ConnectionClosed

from max_library.exceptions import (
    MaxAPIError,
    MaxConnectionError,
    MaxTimeoutError,
    AuthError,
    VerifyCodeWrong,
    UserNotFoundError,
)
from max_library.models.event import IncomingEvent

logger = logging.getLogger("max_library.transport")

DEFAULT_WS_URL = "wss://ws-api.oneme.ru/websocket"
DEFAULT_HEADERS = {
    "Origin": "https://web.oneme.ru",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
}


class MaxTransport:
    """
    Async WebSocket transport implementing packet dispatching by sequence number (seq).
    Eliminates socket recv() collision by having a single background reader loop.
    """

    def __init__(
        self,
        ws_url: str = DEFAULT_WS_URL,
        headers: dict[str, str] | None = None,
        auto_reconnect: bool = True,
        reconnect_initial_delay: float = 1.0,
        reconnect_max_delay: float = 30.0,
        reconnect_backoff_factor: float = 2.0,
        ping_interval: float = 25.0,
        ping_timeout: float = 10.0,
    ):
        self.ws_url = ws_url
        self.headers = headers or DEFAULT_HEADERS.copy()
        self.auto_reconnect = auto_reconnect
        self.reconnect_initial_delay = reconnect_initial_delay
        self.reconnect_max_delay = reconnect_max_delay
        self.reconnect_backoff_factor = reconnect_backoff_factor
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout

        self._ws: Optional[ClientConnection] = None
        self._seq: int = 0
        self._seq_lock = asyncio.Lock()

        self._pending_requests: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.incoming_events_queue: asyncio.Queue[IncomingEvent] = asyncio.Queue()

        self._reader_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._is_connected: bool = False

        self._on_reconnect_callback: Optional[Callable[[], Awaitable[None]]] = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._ws is not None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_on_reconnect(self, callback: Optional[Callable[[], Awaitable[None]]]) -> None:
        """Sets an async callback called after successful reconnection to restore session."""
        self._on_reconnect_callback = callback

    async def next_seq(self) -> int:
        """Generates the next sequential request identifier."""
        async with self._seq_lock:
            current = self._seq
            self._seq += 1
            return current

    @staticmethod
    def generate_cid() -> int:
        """Generates a client message ID (millisecond timestamp)."""
        return int(time.time() * 1000)

    async def connect(self) -> None:
        """Establishes the WebSocket connection and starts background reader."""
        if self._is_connected and self._ws is not None:
            return

        self._is_running = True
        logger.debug(f"Connecting to WebSocket: {self.ws_url}")

        try:
            self._ws = await ws_connect(
                self.ws_url,
                additional_headers=self.headers,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
            )
            self._is_connected = True
            logger.info("WebSocket connected successfully")

            # Start reader loop
            if self._reader_task is None or self._reader_task.done():
                self._reader_task = asyncio.create_task(
                    self._read_loop(), name="max_library_ws_reader"
                )

        except Exception as e:
            self._is_connected = False
            self._ws = None
            logger.error(f"Failed to connect to {self.ws_url}: {e}")
            raise MaxConnectionError(f"Failed to connect to MAX WebSocket: {e}") from e

    async def close(self) -> None:
        """Gracefully closes WebSocket connection and stops background tasks."""
        self._is_running = False
        self._is_connected = False

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            self._reconnect_task = None

        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.debug(f"Error while closing websocket: {e}")
            finally:
                self._ws = None

        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        # Fail all pending requests
        self._fail_all_pending("WebSocket closed by client")
        logger.info("WebSocket transport closed")

    async def __aenter__(self) -> "MaxTransport":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def send_raw_json(self, data: dict[str, Any]) -> None:
        """Sends a JSON-encoded frame over the active WebSocket."""
        if not self.is_connected or not self._ws:
            raise MaxConnectionError("Cannot send frame: WebSocket is not connected")

        payload_str = json.dumps(data, ensure_ascii=False)
        logger.debug(f"WS SEND: {payload_str}")
        await self._ws.send(payload_str)

    async def send_request(
        self,
        opcode: int,
        payload: dict[str, Any],
        timeout: float = 15.0,
        raise_for_error: bool = True,
    ) -> dict[str, Any]:
        """
        Sends an RPC request with a specific opcode and awaits response by matching seq.
        """
        if not self.is_connected:
            raise MaxConnectionError("Cannot send request: WebSocket is not connected")

        seq = await self.next_seq()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending_requests[seq] = future

        frame = {
            "ver": 11,
            "cmd": 0,
            "seq": seq,
            "opcode": opcode,
            "payload": payload,
        }

        try:
            await self.send_raw_json(frame)
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as e:
            logger.warning(f"RPC request timeout: opcode={opcode}, seq={seq}")
            raise MaxTimeoutError(f"Request timeout for opcode {opcode} (seq {seq})") from e
        except ConnectionClosed as e:
            raise MaxConnectionError(f"Connection closed during RPC opcode {opcode}: {e}") from e
        finally:
            self._pending_requests.pop(seq, None)

        if raise_for_error:
            self._check_response_error(response, opcode)

        return response

    @staticmethod
    def _check_response_error(response: dict[str, Any], opcode: int) -> None:
        """Inspects response frame and raises mapped exception if server returned error."""
        payload = response.get("payload", {})
        if not isinstance(payload, dict):
            return

        error = payload.get("error")
        if not error:
            return

        title = payload.get("title")
        message = payload.get("localizedMessage") or payload.get("message")

        logger.warning(f"MAX API Error for opcode {opcode}: error={error}, title={title}")

        if error == "verify.code.wrong":
            raise VerifyCodeWrong(error=error, title=title, message=message, payload=payload, raw_response=response)
        if error in ("auth.error", "token.invalid", "session.not_found"):
            raise AuthError(error=error, title=title, message=message, payload=payload, raw_response=response)
        if "user.not.found" in error or error == "contact.not.found":
            raise UserNotFoundError(error=error, title=title, message=message, payload=payload, raw_response=response)

        raise MaxAPIError(error=error, title=title, message=message, payload=payload, raw_response=response)

    async def _read_loop(self) -> None:
        """Continuous background loop for receiving and dispatching frames."""
        logger.debug("Reader loop started")
        try:
            while self._is_running and self._ws:
                try:
                    raw_msg = await self._ws.recv()
                except ConnectionClosed as e:
                    logger.warning(f"WebSocket closed in reader loop: {e}")
                    break
                except Exception as e:
                    if self._is_running:
                        logger.error(f"WebSocket read error: {e}")
                    break

                if not raw_msg:
                    continue

                try:
                    data = json.loads(raw_msg)
                except Exception as e:
                    logger.warning(f"Failed to parse JSON frame: {raw_msg!r}, error: {e}")
                    continue

                logger.debug(f"WS RECV: {data}")
                self._dispatch_incoming_frame(data)

        finally:
            self._is_connected = False
            self._fail_all_pending("WebSocket disconnected")
            if self._is_running and self.auto_reconnect:
                if self._reconnect_task is None or self._reconnect_task.done():
                    self._reconnect_task = asyncio.create_task(
                        self._reconnect_loop(), name="max_library_reconnect"
                    )

    def _dispatch_incoming_frame(self, data: dict[str, Any]) -> None:
        """Routes frame either to pending RPC Future or to incoming event queue."""
        seq = data.get("seq")
        opcode = data.get("opcode")

        # 1. Match pending RPC request by seq
        if seq is not None and seq in self._pending_requests:
            fut = self._pending_requests.pop(seq)
            if not fut.done():
                fut.set_result(data)
            return

        # 2. Skip trivial ping/pong frames
        if opcode == 1:
            return

        # 3. Push event (opcode 128 for messages, or other server pushes)
        try:
            event = IncomingEvent.model_validate(data)
            self.incoming_events_queue.put_nowait(event)
        except Exception as e:
            logger.error(f"Failed to parse incoming event frame into model: {e}, frame: {data}")

    def _fail_all_pending(self, reason: str) -> None:
        """Cancels/fails all pending RPC futures when connection breaks."""
        for seq, fut in list(self._pending_requests.items()):
            if not fut.done():
                fut.set_exception(MaxConnectionError(reason))
        self._pending_requests.clear()

    async def _reconnect_loop(self) -> None:
        """Handles reconnection with exponential backoff and session recovery."""
        logger.info("Starting automatic reconnection loop...")
        delay = self.reconnect_initial_delay

        while self._is_running and not self._is_connected:
            logger.info(f"Reconnecting in {delay:.1f}s...")
            await asyncio.sleep(delay)

            if not self._is_running:
                break

            try:
                await self.connect()
                logger.info("Reconnection established!")

                # Re-run session recovery callback if registered
                if self._on_reconnect_callback:
                    logger.info("Executing on_reconnect session recovery callback...")
                    await self._on_reconnect_callback()

                logger.info("Session restored successfully after reconnect.")
                break
            except Exception as e:
                logger.warning(f"Reconnection attempt failed: {e}")
                delay = min(delay * self.reconnect_backoff_factor, self.reconnect_max_delay)

        self._reconnect_task = None
