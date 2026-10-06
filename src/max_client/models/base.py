"""
Base Pydantic model for max-client.
"""
from pydantic import BaseModel, ConfigDict


class MaxBaseModel(BaseModel):
    """Base model with common Pydantic v2 configuration for MAX protocol data."""
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
        coerce_numbers_to_str=True,
    )
