"""
max-client: Modern Async Python SDK for MAX Messenger (OneMe).
"""
from max_library.client import MaxClient
from max_library.exceptions import (
    MaxError,
    MaxAPIError,
    MaxConnectionError,
    MaxTimeoutError,
    AuthError,
    VerifyCodeWrong,
    UserNotFoundError,
    ChatNotFoundError,
)
from max_library.filters import filters, Filter
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
    EMOJIS,
)
from max_library import auth

__version__ = "0.5.0"

__all__ = [
    "MaxClient",
    "auth",
    "filters",
    "Filter",
    "MaxError",
    "MaxAPIError",
    "MaxConnectionError",
    "MaxTimeoutError",
    "AuthError",
    "VerifyCodeWrong",
    "UserNotFoundError",
    "ChatNotFoundError",
    "Attachment",
    "Chat",
    "Contact",
    "IncomingEvent",
    "Message",
    "MessageLink",
    "Name",
    "ReactionCounter",
    "Reactions",
    "User",
    "EMOJIS",
]

