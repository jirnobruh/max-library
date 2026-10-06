"""
Incoming and outgoing event frame models for MAX protocol.
"""
from typing import Any
from pydantic import Field
from max_library.models.base import MaxBaseModel


class IncomingEvent(MaxBaseModel):
    """Represents a decoded frame received over WebSocket."""
    ver: int = 11
    cmd: int = 0
    seq: int | None = None
    opcode: int
    payload: dict[str, Any] = Field(default_factory=dict)
