"""
Filters module for max-client.
"""
from typing import Sequence
from max_client.filters.base import Filter, AndFilter, OrFilter, NotFilter, check_filter
from max_client.filters.builtin import (
    TextFilter,
    CommandFilter,
    ChatIdFilter,
    UserIdFilter,
    IsMeFilter,
    HasAttachmentFilter,
    HasTextFilter,
    IsForwardFilter,
    IsReplyFilter,
    IsNotRemovedFilter,
    AnyFilter,
)


class _FiltersNamespace:
    """Convenient factory object for filters, e.g. filters.text('hello')."""

    @staticmethod
    def text(
        query: str,
        exact: bool = True,
        ignore_case: bool = True,
        startswith: bool = False,
        contains: bool = False,
    ) -> TextFilter:
        return TextFilter(
            text=query,
            exact=exact,
            ignore_case=ignore_case,
            startswith=startswith,
            contains=contains,
        )

    @staticmethod
    def command(name: str, prefix: str = "/", ignore_case: bool = True) -> CommandFilter:
        return CommandFilter(command=name, prefix=prefix, ignore_case=ignore_case)

    @staticmethod
    def chat_id(*chat_ids: int | str) -> ChatIdFilter:
        return ChatIdFilter(*chat_ids)

    @staticmethod
    def user_id(*user_ids: int | str) -> UserIdFilter:
        return UserIdFilter(*user_ids)

    @staticmethod
    def is_me() -> IsMeFilter:
        return IsMeFilter()

    me = is_me  # Alias for compatibility

    @staticmethod
    def has_attachment(*types: str) -> HasAttachmentFilter:
        return HasAttachmentFilter(*types)

    @staticmethod
    def has_text() -> HasTextFilter:
        return HasTextFilter()

    @staticmethod
    def is_forward() -> IsForwardFilter:
        return IsForwardFilter()

    @staticmethod
    def is_reply() -> IsReplyFilter:
        return IsReplyFilter()

    @staticmethod
    def is_not_removed() -> IsNotRemovedFilter:
        return IsNotRemovedFilter()

    @staticmethod
    def any() -> AnyFilter:
        return AnyFilter()


filters = _FiltersNamespace()

__all__ = [
    "Filter",
    "AndFilter",
    "OrFilter",
    "NotFilter",
    "check_filter",
    "TextFilter",
    "CommandFilter",
    "ChatIdFilter",
    "UserIdFilter",
    "IsMeFilter",
    "HasAttachmentFilter",
    "HasTextFilter",
    "IsForwardFilter",
    "IsReplyFilter",
    "IsNotRemovedFilter",
    "AnyFilter",
    "filters",
]
