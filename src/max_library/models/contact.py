"""
Contact and Name models for MAX.
"""
from typing import Any
from pydantic import Field, PrivateAttr
from max_library.models.base import MaxBaseModel


class Name(MaxBaseModel):
    """Represents a name structure for a contact."""
    name: str | None = None
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    type: str | None = None


class Contact(MaxBaseModel):
    """Represents contact details in MAX."""
    id: int | str | None = None
    phone: str | int | None = None
    names: list[Name] = Field(default_factory=list)
    description: str | None = None
    account_status: str | int | None = Field(default=None, alias="accountStatus")
    base_url: str | None = Field(default=None, alias="baseUrl")
    base_raw_url: str | None = Field(default=None, alias="baseRawUrl")
    photo_id: str | int | None = Field(default=None, alias="photoId")
    update_time: int | None = Field(default=None, alias="updateTime")
    gender: str | int | None = None
    link: str | None = None
    options: dict[str, Any] | list[Any] | None = None

    _client: Any = PrivateAttr(default=None)

    def bind_client(self, client: Any) -> "Contact":
        self._client = client
        return self

    @property
    def display_name(self) -> str:
        """Returns the best available human-readable name for the contact."""
        if self.names and self.names[0].name:
            return self.names[0].name
        first = self.names[0].first_name if self.names else None
        last = self.names[0].last_name if self.names else None
        if first or last:
            return f"{first or ''} {last or ''}".strip()
        if self.phone:
            return str(self.phone)
        if self.id is not None:
            return f"User {self.id}"
        return "Unknown"

    async def add(self) -> Any:
        """Add this contact."""
        if not self._client or self.id is None:
            raise ValueError("Client or contact ID is missing")
        return await self._client.contact_add(int(self.id))

    async def remove(self) -> bool:
        """Remove this contact."""
        if not self._client or self.id is None:
            raise ValueError("Client or contact ID is missing")
        return await self._client.contact_remove(int(self.id))

    async def block(self) -> bool:
        """Block this contact."""
        if not self._client or self.id is None:
            raise ValueError("Client or contact ID is missing")
        return await self._client.contact_block(int(self.id))

    async def unblock(self) -> bool:
        """Unblock this contact."""
        if not self._client or self.id is None:
            raise ValueError("Client or contact ID is missing")
        return await self._client.contact_unblock(int(self.id))
