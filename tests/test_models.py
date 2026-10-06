"""
Tests for Pydantic models serialization and deserialization.
"""
from max_library.models import (
    Attachment,
    Chat,
    Contact,
    IncomingEvent,
    Message,
    MessageLink,
    Name,
    ReactionCounter,
    Reactions,
    User,
)


def test_attachment_model():
    data = {
        "_type": "PHOTO",
        "name": "photo_123.jpg",
        "baseUrl": "https://img.oneme.ru/photo/123",
        "baseRawUrl": "https://img.oneme.ru/raw/123",
        "photoId": "998877",
        "size": 102400,
        "mimeType": "image/jpeg",
        "width": 1920,
        "height": 1080,
    }
    attach = Attachment.model_validate(data)
    assert attach.type == "PHOTO"
    assert attach.name == "photo_123.jpg"
    assert attach.base_url == "https://img.oneme.ru/photo/123"
    assert attach.photo_id == "998877"
    assert attach.url == "https://img.oneme.ru/photo/123"
    assert attach.is_photo is True
    assert attach.is_video is False
    assert attach.is_file is False


def test_reactions_model():
    data = {
        "reactionInfo": {
            "counters": [
                {"reaction": "👍", "count": 5},
                {"reaction": "🔥", "count": 2},
            ],
            "yourReaction": "👍",
            "totalCount": 7,
        }
    }
    reactions = Reactions.model_validate(data["reactionInfo"])
    assert len(reactions.counters) == 2
    assert reactions.counters[0].reaction == "👍"
    assert reactions.counters[0].count == 5
    assert reactions.your_reaction == "👍"
    assert reactions.total_count == 7


def test_user_and_contact_model():
    data = {
        "id": 12345678,
        "phone": "+79991234567",
        "names": [
            {"name": "Иван Иванов", "firstName": "Иван", "lastName": "Иванов", "type": "USER"}
        ],
        "accountStatus": "ACTIVE",
        "baseUrl": "https://img.oneme.ru/avatar/123",
    }
    user = User.model_validate(data)
    assert user.id == 12345678
    assert user.phone == "+79991234567"
    assert user.display_name == "Иван Иванов"
    assert user.contact.account_status == "ACTIVE"


def test_user_and_contact_numeric_coercion():
    data = {
        "id": 12345678,
        "phone": 79990001122,
        "accountStatus": 0,
        "names": [{"name": "Тест"}],
    }
    user = User.model_validate(data)
    assert str(user.phone) == "79990001122"
    assert user.display_name == "Тест"
    assert str(user.contact.account_status) == "0"


def test_message_model_with_links_and_attachments():
    data = {
        "id": "msg_001",
        "chatId": -100999,
        "sender": 12345678,
        "time": 1700000000000,
        "text": "Hello world!",
        "type": "USER",
        "status": "SENT",
        "attaches": [
            {
                "_type": "FILE",
                "name": "doc.pdf",
                "baseUrl": "https://files.oneme.ru/doc.pdf",
                "size": 2048,
            }
        ],
        "reactionInfo": {
            "counters": [{"reaction": "❤️", "count": 1}],
            "totalCount": 1,
        },
        "link": {
            "type": "FORWARD",
            "messageId": "msg_prev",
            "sender": 87654321,
            "message": {
                "id": "msg_prev",
                "chatId": -100999,
                "text": "Original text",
            },
        },
    }
    msg = Message.model_validate(data)
    assert msg.id == "msg_001"
    assert msg.chat_id == -100999
    assert msg.text == "Hello world!"
    assert msg.is_forward is True
    assert msg.is_reply is False
    assert len(msg.attaches) == 1
    assert msg.attaches[0].is_file is True
    assert msg.link is not None
    assert msg.link.message is not None
    assert msg.link.message.text == "Original text"
    assert msg.reaction_info is not None
    assert msg.reaction_info.total_count == 1


def test_incoming_event_model():
    data = {
        "ver": 11,
        "cmd": 0,
        "seq": 42,
        "opcode": 128,
        "payload": {
            "chatId": 12345,
            "message": {
                "id": "msg_push",
                "chatId": 12345,
                "text": "Incoming push",
            },
        },
    }
    event = IncomingEvent.model_validate(data)
    assert event.ver == 11
    assert event.seq == 42
    assert event.opcode == 128
    assert event.payload["chatId"] == 12345
