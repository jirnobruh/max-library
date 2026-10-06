"""
User model for MAX.
"""
from typing import Any
from pydantic import Field, PrivateAttr, model_validator
from max_client.models.base import MaxBaseModel
from max_client.models.contact import Contact


class User(MaxBaseModel):
    """
    Represents a user profile in MAX.
    """
    contact: Contact
    chat_id: int | str | None = None

    _client: Any = PrivateAttr(default=None)

    @model_validator(mode="before")
    @classmethod
    def _validate_user_data(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "contact" not in data and ("names" in data or "id" in data or "phone" in data):
                return {"contact": data}
        return data

    def bind_client(self, client: Any) -> "User":
        self._client = client
        if self.contact:
            self.contact.bind_client(client)
        return self

    @property
    def id(self) -> int | str | None:
        return self.contact.id if self.contact else None

    @property
    def phone(self) -> str | None:
        return self.contact.phone if self.contact else None

    @property
    def display_name(self) -> str:
        return self.contact.display_name if self.contact else "Unknown"
