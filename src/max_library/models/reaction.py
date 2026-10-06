"""
Reaction models for MAX messages.
"""
from typing import Literal
from pydantic import Field
from max_library.models.base import MaxBaseModel

# Common standard reactions supported by MAX
EMOJIS = Literal[
    '❤️', '👍', '🤣', '🔥', '💯', '😍', '🎉', '⚡',
    '🤩', '🤘', '😎', '🙄', '😐', '😁', '🤪', '😉',
    '🤤', '😇', '😘', '🥰', '🥳', '🌚', '🌝', '😴',
    '🫠', '🤔', '🫡', '😳', '🥱', '🐈', '🐶', '💪',
    '🤞', '👋', '👏', '🤝', '👌', '🙏', '💋', '👑',
    '⭐', '🍷', '🍑', '🤷‍♀️', '🤷‍♂️', '👩‍❤️‍👨', '🦄', '👻',
    '🗿', '👀', '👁️', '🖤', '❤️‍🩹', '🛑', '⛄', '❓',
    '❗️'
]


class ReactionCounter(MaxBaseModel):
    """Counter for a specific emoji reaction."""
    reaction: str
    count: int = 0


class Reactions(MaxBaseModel):
    """Reaction details for a message."""
    counters: list[ReactionCounter] = Field(default_factory=list)
    your_reaction: str | None = Field(default=None, alias="yourReaction")
    total_count: int = Field(default=0, alias="totalCount")
