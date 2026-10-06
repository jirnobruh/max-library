"""
Message models for MAX protocol.
"""
from typing import Any, Optional
from pydantic import Field, PrivateAttr
from max_client.models.base import MaxBaseModel
from max_client.models.attachment import Attachment
from max_client.models.reaction import Reactions
from max_client.models.user import User


class MessageLink(MaxBaseModel):
    """
    Represents linked message data (e.g. REPLY or FORWARD).
    """
    type: str | None = None  # "REPLY", "FORWARD", etc.
    message_id: str | int | None = Field(default=None, alias="messageId")
    message: Optional["Message"] = None
    sender: int | str | None = None
    chat_id: int | str | None = Field(default=None, alias="chatId")


class Message(MaxBaseModel):
    """
    Represents a message in a MAX chat.
    """
    id: str | int | None = None
    chat_id: int | str | None = Field(default=None, alias="chatId")
    sender: int | str | None = None
    time: int | None = None
    text: str | None = ""
    type: str | None = "USER"
    status: str | None = None
    update_time: int | None = Field(default=None, alias="updateTime")
    options: dict[str, Any] | list[Any] | None = None
    cid: int | str | None = None
    attaches: list[Attachment] = Field(default_factory=list)
    reaction_info: Reactions | None = Field(default=None, alias="reactionInfo")
    link: MessageLink | None = None
    elements: list[Any] = Field(default_factory=list)
    user: User | None = None

    _client: Any = PrivateAttr(default=None)

    def bind_client(self, client: Any) -> "Message":
        """Bind client instance to message and child objects."""
        self._client = client
        if self.user:
            self.user.bind_client(client)
        if self.link and self.link.message:
            if self.link.message.chat_id is None:
                self.link.message.chat_id = self.link.chat_id or self.chat_id
            self.link.message.bind_client(client)
        return self

    @property
    def is_forward(self) -> bool:
        return bool(self.link and self.link.type == "FORWARD")

    @property
    def is_reply(self) -> bool:
        return bool(self.link and self.link.type == "REPLY")

    @property
    def is_removed(self) -> bool:
        return self.status == "REMOVED"

    async def reply(self, text: str, notify: bool = True, **kwargs: Any) -> "Message":
        """Replies to this message in the chat."""
        if not self._client:
            raise ValueError("Client is not bound to Message")
        return await self._client.send_message(
            chat_id=self.chat_id,
            text=text,
            reply_id=self.id,
            notify=notify,
            **kwargs,
        )

    async def answer(self, text: str, notify: bool = True, **kwargs: Any) -> "Message":
        """Sends a message in the same chat without quoting."""
        if not self._client:
            raise ValueError("Client is not bound to Message")
        return await self._client.send_message(
            chat_id=self.chat_id,
            text=text,
            notify=notify,
            **kwargs,
        )

    async def delete(self, for_me: bool = False) -> None:
        """Deletes this message."""
        if not self._client or self.id is None:
            raise ValueError("Client or message ID is missing")
        await self._client.delete_message(
            chat_id=self.chat_id,
            message_ids=[str(self.id)],
            for_me=for_me,
        )

    async def edit(self, text: str) -> "Message":
        """Edits this message's text."""
        if not self._client or self.id is None:
            raise ValueError("Client or message ID is missing")
        updated = await self._client.edit_message(
            chat_id=self.chat_id,
            message_id=self.id,
            text=text,
        )
        self.text = updated.text
        return updated

    async def react(self, reaction: str) -> Reactions:
        """Sets a reaction to this message."""
        if not self._client or self.id is None:
            raise ValueError("Client or message ID is missing")
        reactions = await self._client.set_reaction(
            chat_id=self.chat_id,
            message_id=self.id,
            reaction=reaction,
        )
        self.reaction_info = reactions
        return reactions

    async def get_sender(self) -> User | None:
        """Fetches the sender's User profile if not already present."""
        if self.user:
            return self.user
        if not self._client or not self.sender:
            return None
        user = await self._client.get_user(id=self.sender)
        self.user = user
        return user
