"""
Chat model for MAX.
"""
from typing import Any
from pydantic import Field, PrivateAttr
from max_library.models.base import MaxBaseModel


class Chat(MaxBaseModel):
    """
    Represents a chat in MAX.
    """
    id: int | str
    title: str | None = None
    type: str | None = None
    description: str | None = None
    link: str | None = None
    participants_count: int | None = Field(default=None, alias="participantsCount")
    participants: dict[str, Any] | list[Any] | None = None
    owner: int | str | None = None
    base_icon_url: str | None = Field(default=None, alias="baseIconUrl")
    base_raw_icon_url: str | None = Field(default=None, alias="baseRawIconUrl")
    status: str | None = None
    messages: list[Any] = Field(default_factory=list)

    _client: Any = PrivateAttr(default=None)

    @property
    def display_name(self) -> str:
        """Returns the title of the chat, or a formatted fallback identifier."""
        if self.title and self.title.strip():
            return self.title.strip()
        return f"Чат {self.id}"

    def bind_client(self, client: Any) -> "Chat":
        self._client = client
        return self

    async def pin(self) -> bool:
        if not self._client:
            raise ValueError("Client is not bound to Chat")
        return await self._client.pin_chat(self.id)

    async def unpin(self) -> bool:
        if not self._client:
            raise ValueError("Client is not bound to Chat")
        return await self._client.unpin_chat(self.id)

    async def send_message(self, text: str, **kwargs: Any) -> Any:
        if not self._client:
            raise ValueError("Client is not bound to Chat")
        return await self._client.send_message(chat_id=self.id, text=text, **kwargs)
