"""
Tests for filter system and boolean operators (&, |, ~).
"""
import pytest
from max_client.filters import filters
from max_client.models import Attachment, Message, User


@pytest.fixture
def sample_message():
    return Message(
        id="msg_1",
        chatId=1001,
        sender=5555,
        text="/start now",
        type="USER",
        status="NORMAL",
        attaches=[
            Attachment(_type="PHOTO", name="test.jpg", baseUrl="http://example.com/test.jpg")
        ],
    )


@pytest.fixture
def mock_client():
    class DummyClient:
        def __init__(self):
            self.me = User.model_validate({"id": 5555, "names": [{"name": "Self"}]})
    return DummyClient()


@pytest.mark.asyncio
async def test_text_and_command_filter(mock_client, sample_message):
    f_cmd = filters.command("start")
    f_other_cmd = filters.command("help")
    f_exact_text = filters.text("/start now")
    f_wrong_text = filters.text("/start later")

    assert await f_cmd(mock_client, sample_message) is True
    assert await f_other_cmd(mock_client, sample_message) is False
    assert await f_exact_text(mock_client, sample_message) is True
    assert await f_wrong_text(mock_client, sample_message) is False


@pytest.mark.asyncio
async def test_chat_and_user_filters(mock_client, sample_message):
    f_chat = filters.chat_id(1001, 1002)
    f_wrong_chat = filters.chat_id(9999)
    f_user = filters.user_id(5555)
    f_wrong_user = filters.user_id(7777)
    f_is_me = filters.is_me()

    assert await f_chat(mock_client, sample_message) is True
    assert await f_wrong_chat(mock_client, sample_message) is False
    assert await f_user(mock_client, sample_message) is True
    assert await f_wrong_user(mock_client, sample_message) is False
    assert await f_is_me(mock_client, sample_message) is True


@pytest.mark.asyncio
async def test_attachment_and_status_filters(mock_client, sample_message):
    f_has_photo = filters.has_attachment("PHOTO")
    f_has_file = filters.has_attachment("FILE")
    f_has_any_attach = filters.has_attachment()
    f_not_removed = filters.is_not_removed()

    assert await f_has_photo(mock_client, sample_message) is True
    assert await f_has_file(mock_client, sample_message) is False
    assert await f_has_any_attach(mock_client, sample_message) is True
    assert await f_not_removed(mock_client, sample_message) is True


@pytest.mark.asyncio
async def test_filter_boolean_algebra(mock_client, sample_message):
    f_cmd = filters.command("start")
    f_chat = filters.chat_id(1001)
    f_wrong_chat = filters.chat_id(9999)

    # AND operator
    f_and_pass = f_cmd & f_chat
    f_and_fail = f_cmd & f_wrong_chat
    assert await f_and_pass(mock_client, sample_message) is True
    assert await f_and_fail(mock_client, sample_message) is False

    # OR operator
    f_or_pass1 = f_cmd | f_wrong_chat
    f_or_pass2 = f_wrong_chat | f_chat
    f_or_fail = f_wrong_chat | filters.user_id(9999)
    assert await f_or_pass1(mock_client, sample_message) is True
    assert await f_or_pass2(mock_client, sample_message) is True
    assert await f_or_fail(mock_client, sample_message) is False

    # NOT operator
    f_not_fail = ~f_cmd
    f_not_pass = ~f_wrong_chat
    assert await f_not_fail(mock_client, sample_message) is False
    assert await f_not_pass(mock_client, sample_message) is True

    # Complex combination: (cmd & chat) & ~wrong_chat
    f_complex = (f_cmd & f_chat) & ~f_wrong_chat
    assert await f_complex(mock_client, sample_message) is True
