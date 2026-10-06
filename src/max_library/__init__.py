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

__version__ = "0.1.0"

__all__ = [
    "MaxClient",
    "filters",
    "Filter",
    "MaxError",
    "MaxAPIError",
    "MaxConnectionError",
    "MaxTimeoutError",
    "AuthError",
    "VerifyCodeWrong",
    "UserNotFoundError",
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
