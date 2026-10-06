"""
Attachment models for MAX messages.
"""
from typing import Any
from pydantic import Field
from max_client.models.base import MaxBaseModel


class Attachment(MaxBaseModel):
    """
    Represents an attachment in a MAX message (e.g. PHOTO, FILE, VIDEO, AUDIO, STICKER).
    """
    type: str | None = Field(default=None, alias="_type")
    name: str | None = None
    base_url: str | None = Field(default=None, alias="baseUrl")
    base_raw_url: str | None = Field(default=None, alias="baseRawUrl")
    photo_id: str | int | None = Field(default=None, alias="photoId")
    file_id: str | int | None = Field(default=None, alias="fileId")
    token: str | None = None
    photo_token: str | None = Field(default=None, alias="photoToken")
    size: int | None = None
    mime_type: str | None = Field(default=None, alias="mimeType")
    width: int | None = None
    height: int | None = None
    duration: int | float | None = None
    preview_url: str | None = Field(default=None, alias="previewUrl")
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def url(self) -> str | None:
        """Helper to get best available URL for this attachment."""
        return self.base_url or self.base_raw_url or self.preview_url

    async def get_download_url(self, message: Any = None) -> str | None:
        """
        Resolves download URL for this attachment.
        If a direct url is already present, returns it.
        Otherwise requests direct download URL from MAX server via Opcode 88.
        """
        if self.url:
            return self.url
        if not self.file_id or not message:
            return None
        client = getattr(message, "_client", None)
        if not client:
            return None
        return await client.get_file_download_url(
            chat_id=message.chat_id,
            message_id=message.id,
            file_id=self.file_id,
        )

    @property
    def is_photo(self) -> bool:
        return self.type == "PHOTO" or (self.mime_type or "").startswith("image/")

    @property
    def is_video(self) -> bool:
        return self.type == "VIDEO" or (self.mime_type or "").startswith("video/")

    @property
    def is_file(self) -> bool:
        return self.type == "FILE"
