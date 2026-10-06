"""
Base Filter architecture with operator overloading (&, |, ~).
"""
import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable


class Filter(ABC):
    """
    Abstract Base Class for message filters.
    Supports combining filters using logical & (AND), | (OR), and ~ (NOT).
    """

    @abstractmethod
    async def __call__(self, client: Any, message: Any) -> bool:
        """
        Evaluate whether a message passes this filter.
        """
        return True

    def __and__(self, other: "Filter") -> "AndFilter":
        return AndFilter(self, other)

    def __or__(self, other: "Filter") -> "OrFilter":
        return OrFilter(self, other)

    def __invert__(self) -> "NotFilter":
        return NotFilter(self)


async def check_filter(filter_obj: Filter | Callable[..., Any], client: Any, message: Any) -> bool:
    """
    Evaluates a filter or callable that might be synchronous or asynchronous.
    """
    if inspect.iscoroutinefunction(filter_obj.__call__):
        return bool(await filter_obj(client, message))
    res = filter_obj(client, message)
    if inspect.isawaitable(res):
        return bool(await res)
    return bool(res)


class AndFilter(Filter):
    """Logical AND combination of multiple filters."""
    def __init__(self, *filters: Filter):
        self.filters: list[Filter] = []
        for f in filters:
            if isinstance(f, AndFilter):
                self.filters.extend(f.filters)
            else:
                self.filters.append(f)

    async def __call__(self, client: Any, message: Any) -> bool:
        for f in self.filters:
            if not await check_filter(f, client, message):
                return False
        return True

    def __repr__(self) -> str:
        return f"AndFilter({', '.join(repr(f) for f in self.filters)})"


class OrFilter(Filter):
    """Logical OR combination of multiple filters."""
    def __init__(self, *filters: Filter):
        self.filters: list[Filter] = []
        for f in filters:
            if isinstance(f, OrFilter):
                self.filters.extend(f.filters)
            else:
                self.filters.append(f)

    async def __call__(self, client: Any, message: Any) -> bool:
        for f in self.filters:
            if await check_filter(f, client, message):
                return True
        return False

    def __repr__(self) -> str:
        return f"OrFilter({', '.join(repr(f) for f in self.filters)})"


class NotFilter(Filter):
    """Logical NOT negation of a filter."""
    def __init__(self, filter_obj: Filter):
        self.filter = filter_obj

    async def __call__(self, client: Any, message: Any) -> bool:
        return not await check_filter(self.filter, client, message)

    def __repr__(self) -> str:
        return f"NotFilter({repr(self.filter)})"
