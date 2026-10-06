"""
High-level Async MaxClient implementation for MAX Messenger protocol.
"""
import asyncio
import inspect
import logging
import time
from typing import Any, Awaitable, Callable, Optional, Sequence, Union
from uuid import uuid4

from max_library.exceptions import (
    AuthError,
    MaxAPIError,
    MaxConnectionError,
    UserNotFoundError,
    VerifyCodeWrong,
)
from max_library.filters.base import Filter, check_filter
from max_library.models.attachment import Attachment
from max_library.models.chat import Chat
from max_library.models.contact import Contact
from max_library.models.event import IncomingEvent
from max_library.models.message import Message
from max_library.models.reaction import Reactions
from max_library.models.user import User
from max_library.transport.websocket import DEFAULT_WS_URL, MaxTransport

logger = logging.getLogger("max_library.client")

MessageHandler = Callable[["MaxClient", Message], Union[Awaitable[Any], Any]]
ConnectHandler = Callable[["MaxClient"], Union[Awaitable[Any], Any]]


class MaxClient:
    """
    Main asynchronous client for MAX Messenger.
    """

    def __init__(
        self,
        token: str | None = None,
        phone: str | None = None,
        base_ws_url: str = DEFAULT_WS_URL,
        auto_reconnect: bool = True,
        num_workers: int = 4,
        app_version: str = "4.8.42",
        device_id: str | None = None,
    ):
        self.token = token
        self.phone = phone
        self.app_version = app_version
        self.device_id = device_id or str(uuid4())
        self.num_workers = num_workers

        self.transport = MaxTransport(
            ws_url=base_ws_url,
            auto_reconnect=auto_reconnect,
        )
        self.transport.set_on_reconnect(self._restore_session_on_reconnect)

        self.me: Optional[User] = None
        self._is_running = False

        self._message_handlers: list[tuple[Optional[Filter | Callable], MessageHandler]] = []
        self._connect_handlers: list[ConnectHandler] = []
        self._worker_tasks: list[asyncio.Task] = []

    @property
    def is_connected(self) -> bool:
        return self.transport.is_connected

    @property
    def is_logged_in(self) -> bool:
        return self.is_connected and self.me is not None

    async def __aenter__(self) -> "MaxClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # =========================================================================
    # Lifecycle & Connection Management
    # =========================================================================

    async def start(self) -> None:
        """
        Connects to the server, performs handshake and token authentication if token is set,
        and starts background event consumer workers.
        """
        if self._is_running:
            return

        self._is_running = True
        logger.info("Starting MaxClient...")

        # 1. Connect WebSocket
        await self.transport.connect()

        # 2. Send Opcode 6 (Handshake)
        await self._send_handshake()

        # 3. If token is provided, initialize session (Opcode 19)
        if self.token:
            await self._init_session_by_token(self.token)

        # 4. Start event worker pool
        self._start_workers()

        # 5. Trigger on_connect handlers
        await self._notify_connect_handlers()

        logger.info("MaxClient started successfully.")

    async def close(self) -> None:
        """Stops event workers and closes the WebSocket connection."""
        self._is_running = False
        logger.info("Closing MaxClient...")

        # Stop workers
        for task in self._worker_tasks:
            task.cancel()
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()

        # Close transport
        await self.transport.close()
        self.me = None
        logger.info("MaxClient closed.")

    async def run_forever(self) -> None:
        """Convenience method to start client and keep running until interrupted."""
        await self.start()
        try:
            while self._is_running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.close()

    def _start_workers(self) -> None:
        """Spawns background worker pool to process events from the transport queue."""
        for i in range(self.num_workers):
            task = asyncio.create_task(self._event_worker(i), name=f"max_library_worker_{i}")
            self._worker_tasks.append(task)

    async def _event_worker(self, worker_id: int) -> None:
        """Worker loop processing events from the queue."""
        logger.debug(f"Event worker #{worker_id} started")
        while self._is_running:
            try:
                event = await self.transport.incoming_events_queue.get()
                try:
                    await self._process_incoming_event(event)
                finally:
                    self.transport.incoming_events_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event worker #{worker_id}: {e}", exc_info=True)

    async def _process_incoming_event(self, event: IncomingEvent) -> None:
        """Dispatches an incoming event to relevant registered handlers."""
        # Opcode 128: Incoming message push
        if event.opcode == 128:
            payload = event.payload
            chat_id = payload.get("chatId")
            msg_dict = payload.get("message", {})
            if not isinstance(msg_dict, dict):
                return

            try:
                # Merge chatId into message if not present
                if "chatId" not in msg_dict and chat_id is not None:
                    msg_dict["chatId"] = chat_id

                # If link message is present, propagate chatId if missing
                link = msg_dict.get("link")
                if isinstance(link, dict):
                    link_msg = link.get("message")
                    if isinstance(link_msg, dict) and "chatId" not in link_msg:
                        link_msg["chatId"] = link.get("chatId") or chat_id

                message = Message.model_validate(msg_dict)
                message.bind_client(self)
            except Exception as e:
                logger.error(f"Failed to parse incoming Message payload: {e}, data: {msg_dict}")
                return

            await self._dispatch_message(message)

    async def _dispatch_message(self, message: Message) -> None:
        """Evaluates filters and executes matching message handlers."""
        for filter_obj, handler in self._message_handlers:
            try:
                if filter_obj is not None:
                    passed = await check_filter(filter_obj, self, message)
                    if not passed:
                        continue

                # Execute handler safely
                if inspect.iscoroutinefunction(handler):
                    await handler(self, message)
                else:
                    res = handler(self, message)
                    if inspect.isawaitable(res):
                        await res
            except Exception as e:
                logger.error(f"Error executing message handler {handler.__name__}: {e}", exc_info=True)

    async def _notify_connect_handlers(self) -> None:
        """Executes all registered on_connect callbacks."""
        for handler in self._connect_handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(self)
                else:
                    res = handler(self)
                    if inspect.isawaitable(res):
                        await res
            except Exception as e:
                logger.error(f"Error executing connect handler {handler.__name__}: {e}", exc_info=True)

    # =========================================================================
    # Handshake & Protocol Session
    # =========================================================================

    async def _send_handshake(self) -> dict[str, Any]:
        """Sends Opcode 6 (Handshake/UserAgent)."""
        payload = {
            "userAgent": {
                "deviceType": "WEB",
                "locale": "en",
                "osVersion": "Windows",
                "deviceName": "WebMax Lib",
                "headerUserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                "deviceLocale": "en",
                "appVersion": self.app_version,
                "screen": "1920x1080 1.0x",
                "timezone": "UTC",
            },
            "deviceId": self.device_id,
        }
        resp = await self.transport.send_request(opcode=6, payload=payload)
        return resp

    async def _init_session_by_token(self, token: str) -> User:
        """Sends Opcode 19 to establish interactive session and retrieve self profile."""
        payload = {
            "interactive": True,
            "token": token,
            "chatsSync": 0,
            "contactsSync": 0,
            "presenceSync": 0,
            "draftsSync": 0,
            "chatsCount": 40,
        }
        resp = await self.transport.send_request(opcode=19, payload=payload)
        resp_payload = resp.get("payload", {})
        profile = resp_payload.get("profile")
        if not profile:
            raise AuthError(
                error="invalid_profile_response",
                message="Server response did not contain user profile",
                payload=resp_payload,
            )

        user = User.model_validate(profile).bind_client(self)
        self.me = user
        logger.info(f"Authenticated as: {user.display_name} (ID: {user.id})")
        return user

    async def _restore_session_on_reconnect(self) -> None:
        """Internal callback invoked by transport on auto-reconnection."""
        logger.info("Re-performing handshake and session init after reconnect...")
        await self._send_handshake()
        if self.token:
            await self._init_session_by_token(self.token)
            await self._notify_connect_handlers()

    # =========================================================================
    # Authentication (Opcode 17 & Opcode 18)
    # =========================================================================

    async def auth(
        self,
        phone: str,
        code_callback: Optional[Callable[[], Union[Awaitable[str], str]]] = None,
    ) -> User:
        """
        Performs full SMS verification code authentication flow.
        """
        if not self.is_connected:
            await self.transport.connect()
            await self._send_handshake()

        # Step 1: Start auth (Opcode 17)
        logger.info(f"Requesting SMS code for phone {phone}...")
        resp_17 = await self.transport.send_request(
            opcode=17,
            payload={
                "phone": phone,
                "type": "START_AUTH",
                "language": "ru",
            },
        )
        temp_token = resp_17.get("payload", {}).get("token")
        if not temp_token:
            raise AuthError(
                error="no_auth_token",
                message="Failed to obtain temporary auth token from server",
                payload=resp_17.get("payload"),
            )

        # Step 2: Obtain code
        if code_callback is not None:
            if inspect.iscoroutinefunction(code_callback):
                code = await code_callback()
            else:
                code = code_callback()
                if inspect.isawaitable(code):
                    code = await code
        else:
            # Fallback for CLI interactive mode
            code = input(f"Enter verification code for {phone}: ")

        code = str(code).strip()

        # Step 3: Check code (Opcode 18)
        logger.info("Verifying code...")
        resp_18 = await self.transport.send_request(
            opcode=18,
            payload={
                "token": temp_token,
                "verifyCode": code,
                "authTokenType": "CHECK_CODE",
            },
        )

        p18 = resp_18.get("payload", {})
        login_token = (
            p18.get("tokenAttrs", {}).get("LOGIN", {}).get("token")
            or p18.get("token")
        )
        if not login_token:
            raise AuthError(
                error="no_login_token",
                message="Verification succeeded but login token was missing in response",
                payload=p18,
            )

        self.token = login_token
        profile = p18.get("profile") or {}
        user = User.model_validate(profile).bind_client(self)
        self.me = user

        # Start workers & notify
        self._start_workers()
        await self._notify_connect_handlers()

        return user

    # =========================================================================
    # Messaging (Opcode 64, 66, 67, 49)
    # =========================================================================

    async def send_message(
        self,
        chat_id: int | str,
        text: str = "",
        reply_id: str | int | None = None,
        notify: bool = True,
        cid: int | None = None,
        attaches: Optional[list[Union[Attachment, dict[str, Any]]]] = None,
    ) -> Message:
        """
        Sends a message to the specified chat (Opcode 64).
        """
        formatted_attaches: list[dict[str, Any]] = []
        if attaches:
            for a in attaches:
                if isinstance(a, Attachment):
                    formatted_attaches.append(a.model_dump(by_alias=True, exclude_none=True))
                elif isinstance(a, dict):
                    formatted_attaches.append(a)

        msg_payload: dict[str, Any] = {
            "text": text,
            "cid": cid or MaxTransport.generate_cid(),
            "elements": [],
            "attaches": formatted_attaches,
        }

        if reply_id is not None:
            msg_payload["link"] = {
                "type": "REPLY",
                "messageId": str(reply_id),
            }

        req_payload = {
            "chatId": int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
            "message": msg_payload,
            "notify": notify,
        }

        resp = await self.transport.send_request(opcode=64, payload=req_payload)
        resp_payload = resp.get("payload", {})
        raw_msg = resp_payload.get("message", {})
        if "chatId" not in raw_msg and "chatId" in resp_payload:
            raw_msg["chatId"] = resp_payload["chatId"]
        elif "chatId" not in raw_msg:
            raw_msg["chatId"] = chat_id

        msg = Message.model_validate(raw_msg).bind_client(self)
        return msg

    async def edit_message(
        self,
        chat_id: int | str,
        message_id: str | int,
        text: str,
    ) -> Message:
        """
        Edits the text of an existing message (Opcode 67).
        """
        req_payload = {
            "chatId": int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
            "messageId": str(message_id),
            "text": text,
            "elements": [],
            "attachments": [],
        }
        resp = await self.transport.send_request(opcode=67, payload=req_payload)
        resp_payload = resp.get("payload", {})
        raw_msg = resp_payload.get("message", {})
        if "chatId" not in raw_msg:
            raw_msg["chatId"] = chat_id

        msg = Message.model_validate(raw_msg).bind_client(self)
        return msg

    async def delete_message(
        self,
        chat_id: int | str,
        message_ids: Union[Sequence[str | int], str, int],
        for_me: bool = False,
    ) -> None:
        """
        Deletes one or more messages in a chat (Opcode 66).
        """
        if isinstance(message_ids, (str, int)):
            ids_list = [str(message_ids)]
        else:
            ids_list = [str(mid) for mid in message_ids]

        req_payload = {
            "chatId": int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
            "messageIds": ids_list,
            "forMe": for_me,
        }
        await self.transport.send_request(opcode=66, payload=req_payload)

    async def get_history(
        self,
        chat_id: int | str,
        backward: int = 30,
        forward: int = 0,
        from_time: int | None = None,
    ) -> list[Message]:
        """
        Retrieves message history for a chat (Opcode 49).
        """
        req_payload = {
            "chatId": int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
            "from": from_time or int(time.time() * 1000),
            "forward": forward,
            "backward": backward,
            "getMessages": True,
        }
        resp = await self.transport.send_request(opcode=49, payload=req_payload)
        raw_messages = resp.get("payload", {}).get("messages", [])
        messages: list[Message] = []
        for raw in raw_messages:
            if "chatId" not in raw:
                raw["chatId"] = chat_id
            messages.append(Message.model_validate(raw).bind_client(self))
        return messages

    async def get_file_download_url(
        self,
        chat_id: int | str,
        message_id: int | str,
        file_id: int | str,
        item_type: str = "REGULAR",
    ) -> str | None:
        """
        Retrieves direct download URL for a file attachment (Opcode 88).
        """
        cid = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
        fid = int(file_id) if str(file_id).isdigit() else file_id
        mid = str(message_id)
        resp = await self.transport.send_request(
            opcode=88,
            payload={
                "chatId": cid,
                "messageId": mid,
                "fileId": fid,
                "itemType": item_type,
            },
        )
        return resp.get("payload", {}).get("url")

    # =========================================================================
    # Reactions (Opcode 178)
    # =========================================================================

    async def set_reaction(
        self,
        chat_id: int | str,
        message_id: str | int,
        reaction: str,
    ) -> Reactions:
        """
        Sets an emoji reaction on a message (Opcode 178).
        """
        req_payload = {
            "chatId": int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
            "messageId": str(message_id),
            "reaction": {
                "reactionType": "EMOJI",
                "id": reaction,
            },
        }
        resp = await self.transport.send_request(opcode=178, payload=req_payload)
        reaction_info = resp.get("payload", {}).get("reactionInfo", {})
        return Reactions.model_validate(reaction_info)

    # =========================================================================
    # User & Contacts (Opcode 32, 46, 34)
    # =========================================================================

    async def get_user(
        self,
        id: int | str | None = None,
        phone: str | None = None,
        chat_id: int | None = None,
    ) -> User:
        """
        Retrieves a user profile by contact ID (Opcode 32) or phone number (Opcode 46).
        """
        if id is not None:
            contact_id = int(id) if str(id).isdigit() else id
            resp = await self.transport.send_request(
                opcode=32,
                payload={"contactIds": [contact_id]},
            )
            contacts = resp.get("payload", {}).get("contacts", [])
            if not contacts:
                raise UserNotFoundError(error="user.not.found", message=f"User with ID {id} not found")
            return User.model_validate(contacts[0]).bind_client(self)

        if phone is not None:
            resp = await self.transport.send_request(
                opcode=46,
                payload={"phone": str(phone)},
            )
            contact = resp.get("payload", {}).get("contact")
            if not contact:
                raise UserNotFoundError(error="user.not.found", message=f"User with phone {phone} not found")
            contact["phone"] = phone
            return User.model_validate(contact).bind_client(self)

        if chat_id is not None:
            if not self.me or not self.me.id:
                raise ValueError("Client self ID unknown. Authenticate first.")
            calculated_id = int(self.me.id) ^ chat_id
            return await self.get_user(id=calculated_id)

        raise ValueError("Either 'id', 'phone', or 'chat_id' must be provided")

    async def contact_add(self, user_id: int | str) -> User:
        """Adds a contact (Opcode 34)."""
        uid = int(user_id) if str(user_id).isdigit() else user_id
        resp = await self.transport.send_request(
            opcode=34,
            payload={"contactId": uid, "action": "ADD"},
        )
        contact_data = resp.get("payload", {}).get("contact", {})
        return User.model_validate(contact_data).bind_client(self)

    async def contact_remove(self, user_id: int | str) -> bool:
        """Removes a contact (Opcode 34)."""
        uid = int(user_id) if str(user_id).isdigit() else user_id
        await self.transport.send_request(
            opcode=34,
            payload={"contactId": uid, "action": "REMOVE"},
        )
        return True

    async def contact_block(self, user_id: int | str) -> bool:
        """Blocks a contact (Opcode 34)."""
        uid = int(user_id) if str(user_id).isdigit() else user_id
        await self.transport.send_request(
            opcode=34,
            payload={"contactId": uid, "action": "BLOCK"},
        )
        return True

    async def contact_unblock(self, user_id: int | str) -> bool:
        """Unblocks a contact (Opcode 34)."""
        uid = int(user_id) if str(user_id).isdigit() else user_id
        await self.transport.send_request(
            opcode=34,
            payload={"contactId": uid, "action": "UNBLOCK"},
        )
        return True

    # =========================================================================
    # Chat Actions (Opcode 22, 20)
    # =========================================================================

    async def pin_chat(self, chat_id: int | str) -> bool:
        """Pins a chat (Opcode 22)."""
        await self.transport.send_request(
            opcode=22,
            payload={"settings": {"chats": {str(chat_id): {"favIndex": int(time.time() * 1000)}}}},
        )
        return True

    async def unpin_chat(self, chat_id: int | str) -> bool:
        """Unpins a chat (Opcode 22)."""
        await self.transport.send_request(
            opcode=22,
            payload={"settings": {"chats": {str(chat_id): {"favIndex": 0}}}},
        )
        return True

    async def session_exit(self) -> bool:
        """Terminates active session token on server (Opcode 20)."""
        await self.transport.send_request(opcode=20, payload={})
        await self.close()
        return True

    # =========================================================================
    # Decorators
    # =========================================================================

    def on_message(
        self,
        filters: Optional[Filter | Callable] = None,
    ) -> Callable[[MessageHandler], MessageHandler]:
        """
        Decorator to register a message event handler.
        """
        def decorator(func: MessageHandler) -> MessageHandler:
            self._message_handlers.append((filters, func))
            return func

        return decorator

    def on_connect(self, func: ConnectHandler) -> ConnectHandler:
        """
        Decorator to register a callback executed when client connects and authenticates.
        """
        self._connect_handlers.append(func)
        return func
