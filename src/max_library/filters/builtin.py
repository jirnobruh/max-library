"""
Built-in message filters.
"""
from typing import Any, Sequence
from max_library.filters.base import Filter


class TextFilter(Filter):
    """Matches message text."""
    def __init__(
        self,
        text: str,
        exact: bool = True,
        ignore_case: bool = True,
        startswith: bool = False,
        contains: bool = False,
    ):
        self.raw_text = text
        self.text = text.lower() if ignore_case else text
        self.exact = exact
        self.ignore_case = ignore_case
        self.startswith = startswith
        self.contains = contains

    async def __call__(self, client: Any, message: Any) -> bool:
        if not message.text:
            return False
        msg_text = message.text.lower() if self.ignore_case else message.text
        if self.startswith:
            return msg_text.startswith(self.text)
        if self.contains:
            return self.text in msg_text
        if self.exact:
            return msg_text == self.text
        return self.text in msg_text

    def __repr__(self) -> str:
        return f"TextFilter(text={self.raw_text!r}, exact={self.exact})"


class CommandFilter(Filter):
    """Matches commands like /start or !help."""
    def __init__(self, command: str, prefix: str = "/", ignore_case: bool = True):
        self.prefix = prefix
        self.raw_command = command
        self.command = command.lower() if ignore_case else command
        self.ignore_case = ignore_case
        self.full_command = f"{self.prefix}{self.command}"

    async def __call__(self, client: Any, message: Any) -> bool:
        if not message.text:
            return False
        msg_text = message.text.lower() if self.ignore_case else message.text
        if not msg_text.startswith(self.full_command):
            return False
        # Ensure command is bounded by space, newline, or end of string
        rest = msg_text[len(self.full_command):]
        return len(rest) == 0 or rest[0].isspace()

    def __repr__(self) -> str:
        return f"CommandFilter({self.prefix}{self.raw_command})"


class ChatIdFilter(Filter):
    """Matches one or more chat IDs."""
    def __init__(self, *chat_ids: int | str):
        self.chat_ids = {str(cid) for cid in chat_ids}

    async def __call__(self, client: Any, message: Any) -> bool:
        return str(message.chat_id) in self.chat_ids

    def __repr__(self) -> str:
        return f"ChatIdFilter({self.chat_ids})"


class UserIdFilter(Filter):
    """Matches sender user ID(s)."""
    def __init__(self, *user_ids: int | str):
        self.user_ids = {str(uid) for uid in user_ids}

    async def __call__(self, client: Any, message: Any) -> bool:
        if message.sender is None:
            return False
        return str(message.sender) in self.user_ids

    def __repr__(self) -> str:
        return f"UserIdFilter({self.user_ids})"


class IsMeFilter(Filter):
    """Matches messages sent by the authenticated client user."""
    async def __call__(self, client: Any, message: Any) -> bool:
        if not client or not getattr(client, "me", None):
            return False
        my_id = getattr(client.me, "id", None)
        if my_id is None and hasattr(client.me, "contact"):
            my_id = getattr(client.me.contact, "id", None)
        return my_id is not None and str(message.sender) == str(my_id)

    def __repr__(self) -> str:
        return "IsMeFilter()"


class HasAttachmentFilter(Filter):
    """Matches messages containing attachments, optionally filtered by type."""
    def __init__(self, *types: str):
        self.types = {t.upper() for t in types}

    async def __call__(self, client: Any, message: Any) -> bool:
        attaches = getattr(message, "attaches", [])
        if not attaches:
            return False
        if not self.types:
            return True
        return any((getattr(a, "type", None) or "").upper() in self.types for a in attaches)

    def __repr__(self) -> str:
        return f"HasAttachmentFilter({self.types})"


class HasTextFilter(Filter):
    """Matches messages that have non-empty text."""
    async def __call__(self, client: Any, message: Any) -> bool:
        return bool(message.text and message.text.strip())

    def __repr__(self) -> str:
        return "HasTextFilter()"


class IsForwardFilter(Filter):
    """Matches forwarded messages."""
    async def __call__(self, client: Any, message: Any) -> bool:
        return bool(getattr(message, "is_forward", False))

    def __repr__(self) -> str:
        return "IsForwardFilter()"


class IsReplyFilter(Filter):
    """Matches reply messages."""
    async def __call__(self, client: Any, message: Any) -> bool:
        return bool(getattr(message, "is_reply", False))

    def __repr__(self) -> str:
        return "IsReplyFilter()"


class IsNotRemovedFilter(Filter):
    """Matches messages with status != 'REMOVED'."""
    async def __call__(self, client: Any, message: Any) -> bool:
        return getattr(message, "status", None) != "REMOVED"

    def __repr__(self) -> str:
        return "IsNotRemovedFilter()"


class AnyFilter(Filter):
    """Matches any message."""
    async def __call__(self, client: Any, message: Any) -> bool:
        return True

    def __repr__(self) -> str:
        return "AnyFilter()"
