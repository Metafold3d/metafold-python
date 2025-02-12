from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union


def asdatetime(s: Union[str, datetime]) -> datetime:
    """Parse Metafold API datetime.

    Note datetime strings returned by the Metafold API are RFC 1123 formatted,
    times are always in GMT.

    Returns:
        UTC datetime.
    """
    if isinstance(s, datetime):
        return s
    return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)


def asdict(**kwargs: Any) -> dict[str, Any]:
    """Convert present kwargs to dictionary."""
    d = {}
    for k, v in kwargs.items():
        if v is not None:
            d[k] = v
    return d


T = TypeVar("T")
U = TypeVar("U")


def optional(f: Callable[[T], U]) -> Callable[[Optional[T]], Optional[U]]:
    """Decorator to generate converters that accept optional values."""
    @wraps(f)
    def decorator(v: Optional[T]) -> Optional[U]:
        if v is None:
            return None
        return f(v)

    return decorator


optional_datetime = optional(asdatetime)
