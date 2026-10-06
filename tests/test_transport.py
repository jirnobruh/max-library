"""
Unit tests for MaxTransport RPC dispatcher and WebSocket frame routing.
"""
import asyncio
import json
import pytest
import pytest_asyncio
from max_client.exceptions import MaxAPIError, MaxTimeoutError, VerifyCodeWrong
from max_client.transport.websocket import MaxTransport


class MockWebSocket:
    """Mock WebSocket client connection simulating duplex async frames."""

    def __init__(self):
        self.sent_frames: list[dict] = []
        self.recv_queue: asyncio.Queue[str] = asyncio.Queue()
        self.is_closed = False

    async def send(self, data: str):
        self.sent_frames.append(json.loads(data))

    async def recv(self) -> str:
        return await self.recv_queue.get()

    async def close(self):
        self.is_closed = True

    def put_incoming(self, frame_dict: dict):
        self.recv_queue.put_nowait(json.dumps(frame_dict))


@pytest.fixture
def mock_ws():
    return MockWebSocket()


@pytest_asyncio.fixture
async def transport(mock_ws):
    t = MaxTransport(auto_reconnect=False)
    t._ws = mock_ws
    t._is_connected = True
    t._is_running = True
    t._reader_task = asyncio.create_task(t._read_loop())
    yield t
    await t.close()


@pytest.mark.asyncio
async def test_rpc_request_response_matching(transport, mock_ws):
    """Test that send_request sends frame with seq and awaits matching response."""
    async def server_response_sim():
        # Wait until request is sent
        while not mock_ws.sent_frames:
            await asyncio.sleep(0.01)

        req = mock_ws.sent_frames[0]
        assert req["opcode"] == 64
        req_seq = req["seq"]

        # Put response with matching seq
        mock_ws.put_incoming({
            "ver": 11,
            "cmd": 0,
            "seq": req_seq,
            "opcode": 64,
            "payload": {
                "chatId": 100,
                "message": {"id": "msg_123", "text": "Hello response"},
            },
        })

    resp_task = asyncio.create_task(server_response_sim())

    resp = await transport.send_request(
        opcode=64,
        payload={"chatId": 100, "message": {"text": "Hello"}},
        timeout=2.0,
    )
    await resp_task

    assert resp["payload"]["message"]["id"] == "msg_123"
    assert resp["payload"]["message"]["text"] == "Hello response"


@pytest.mark.asyncio
async def test_rpc_interleaved_concurrent_requests(transport, mock_ws):
    """Test multiple concurrent requests matching by seq even when responses arrive out of order."""
    async def server_response_sim():
        while len(mock_ws.sent_frames) < 3:
            await asyncio.sleep(0.01)

        req0 = mock_ws.sent_frames[0]
        req1 = mock_ws.sent_frames[1]
        req2 = mock_ws.sent_frames[2]

        # Respond in reverse order: 2, 0, 1
        mock_ws.put_incoming({"ver": 11, "cmd": 0, "seq": req2["seq"], "opcode": 49, "payload": {"tag": "req2"}})
        mock_ws.put_incoming({"ver": 11, "cmd": 0, "seq": req0["seq"], "opcode": 49, "payload": {"tag": "req0"}})
        mock_ws.put_incoming({"ver": 11, "cmd": 0, "seq": req1["seq"], "opcode": 49, "payload": {"tag": "req1"}})

    resp_task = asyncio.create_task(server_response_sim())

    r0, r1, r2 = await asyncio.gather(
        transport.send_request(opcode=49, payload={"n": 0}),
        transport.send_request(opcode=49, payload={"n": 1}),
        transport.send_request(opcode=49, payload={"n": 2}),
    )
    await resp_task

    assert r0["payload"]["tag"] == "req0"
    assert r1["payload"]["tag"] == "req1"
    assert r2["payload"]["tag"] == "req2"


@pytest.mark.asyncio
async def test_rpc_timeout_handling(transport):
    """Test that send_request raises MaxTimeoutError when server does not respond."""
    with pytest.raises(MaxTimeoutError):
        await transport.send_request(opcode=99, payload={}, timeout=0.1)


@pytest.mark.asyncio
async def test_rpc_server_error_mapping(transport, mock_ws):
    """Test that server error responses are parsed into specific MaxAPIError subclasses."""
    async def server_error_sim():
        while not mock_ws.sent_frames:
            await asyncio.sleep(0.01)
        req = mock_ws.sent_frames[0]
        mock_ws.put_incoming({
            "ver": 11,
            "cmd": 0,
            "seq": req["seq"],
            "opcode": 18,
            "payload": {
                "error": "verify.code.wrong",
                "title": "Неверный код",
            },
        })

    task = asyncio.create_task(server_error_sim())
    with pytest.raises(VerifyCodeWrong) as exc_info:
        await transport.send_request(opcode=18, payload={}, timeout=2.0)
    await task

    assert exc_info.value.error == "verify.code.wrong"
    assert exc_info.value.title == "Неверный код"


@pytest.mark.asyncio
async def test_push_event_routing_to_queue(transport, mock_ws):
    """Test that incoming push events (e.g. opcode 128) go into incoming_events_queue."""
    mock_ws.put_incoming({
        "ver": 11,
        "cmd": 0,
        "opcode": 128,
        "payload": {
            "chatId": 500,
            "message": {"id": "push_1", "text": "Incoming message"},
        },
    })

    event = await asyncio.wait_for(transport.incoming_events_queue.get(), timeout=1.0)
    assert event.opcode == 128
    assert event.payload["chatId"] == 500
    assert event.payload["message"]["id"] == "push_1"
