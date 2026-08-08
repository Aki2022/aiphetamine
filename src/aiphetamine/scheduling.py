"""Pure fixed two-hour boundary calculation."""

from __future__ import annotations

from datetime import datetime, timedelta


def next_boundary(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone()
    next_hour = ((local.hour // 2) + 1) * 2
    if next_hour >= 24:
        return local.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
    return local.replace(hour=next_hour, minute=0, second=0, microsecond=0)
