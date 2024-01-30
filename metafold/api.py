from datetime import datetime, timezone
from typing import Any


def asdatetime(s: str | datetime) -> datetime:
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
