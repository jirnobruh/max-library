"""
Unit tests for high-level MaxClient operations and message handling.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock

from max_library import MaxClient, filters
from max_library.models import Message, User
from max_library.models.event import IncomingEvent


@pytest.fixture
def client():
    return MaxClient(token="fake_token_123")


@pytest.mark.asyncio
async def test_client_send_message():
    client = MaxClient(token="test_token")
    mock_send = AsyncMock(return_value={
        "ver": 11,
        "cmd": 0,
        "seq": 1,
        "opcode": 64,
        "payload": {
            "chatId": 12345,
            "message": {
                "id": "sent_100",
                "chatId": 12345,
                "text": "Hello bot",
                "time": 1700000000,
            },
        },
    })
    client.transport.send_request = mock_send
    client.transport._is_connected = True
    client.transport._ws = object()

    msg = await client.send_message(chat_id=12345, text="Hello bot")
    assert isinstance(msg, Message)
    assert msg.id == "sent_100"
    assert msg.text == "Hello bot"
    assert msg.chat_id == 12345

    # Check payload sent to transport
    mock_send.assert_called_once()
    call_args = mock_send.call_args[1]
    assert call_args["opcode"] == 64
    assert call_args["payload"]["chatId"] == 12345
    assert call_args["payload"]["message"]["text"] == "Hello bot"


@pytest.mark.asyncio
async def test_client_edit_and_delete_message():
    client = MaxClient(token="test_token")
    mock_send = AsyncMock(return_value={
        "ver": 11,
        "cmd": 0,
        "seq": 2,
        "opcode": 67,
        "payload": {
            "chatId": 12345,
            "message": {
                "id": "sent_100",
                "chatId": 12345,
                "text": "Updated text",
            },
        },
    })
    client.transport.send_request = mock_send
    client.transport._is_connected = True
    client.transport._ws = object()

    # Edit
    edited = await client.edit_message(chat_id=12345, message_id="sent_100", text="Updated text")
    assert edited.text == "Updated text"

    # Delete
    await client.delete_message(chat_id=12345, message_ids=["sent_100"])
    assert mock_send.call_count == 2
    del_args = mock_send.call_args[1]
    assert del_args["opcode"] == 66
    assert del_args["payload"]["messageIds"] == ["sent_100"]


@pytest.mark.asyncio
async def test_client_on_message_dispatching():
    client = MaxClient(token="test_token", num_workers=1)
    client._is_running = True
    client._start_workers()

    received_messages: list[Message] = []

    @client.on_message(filters.command("echo"))
    async def handle_echo(c: MaxClient, m: Message):
        received_messages.append(m)

    # Simulate incoming push event frame (Opcode 128)
    event = IncomingEvent(
        ver=11,
        cmd=0,
        opcode=128,
        payload={
            "chatId": 777,
            "message": {
                "id": "m_echo_1",
                "chatId": 777,
                "text": "/echo hello",
                "type": "USER",
            },
        },
    )

    await client.transport.incoming_events_queue.put(event)

    # Wait briefly for worker to process event
    for _ in range(20):
        if received_messages:
            break
        await asyncio.sleep(0.05)

    assert len(received_messages) == 1
    assert received_messages[0].id == "m_echo_1"
    assert received_messages[0].text == "/echo hello"

    await client.close()


@pytest.mark.asyncio
async def test_client_auth_flow():
    client = MaxClient()
    mock_send = AsyncMock()

    # Step 1 response for opcode 17
    resp_17 = {
        "ver": 11,
        "opcode": 17,
        "payload": {"token": "temp_auth_token"},
    }
    # Step 2 response for opcode 18
    resp_18 = {
        "ver": 11,
        "opcode": 18,
        "payload": {
            "tokenAttrs": {"LOGIN": {"token": "permanent_login_token"}},
            "profile": {
                "id": 9999,
                "phone": "+79990000000",
                "names": [{"name": "Test User"}],
            },
        },
    }

    mock_send.side_effect = [resp_17, resp_18]
    client.transport.send_request = mock_send
    client.transport._is_connected = True
    client.transport._ws = object()

    async def provide_code():
        return "12345"

    user = await client.auth(phone="+79990000000", code_callback=provide_code)
    assert user.id == 9999
    assert user.display_name == "Test User"
    assert client.token == "permanent_login_token"
    assert client.me is not None
    assert client.me.id == 9999

    await client.close()
