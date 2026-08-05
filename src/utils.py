from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, TypeVar

T = TypeVar("T")
TWOPLACES = Decimal("0.01")


def stable_unique(values: Iterable[T]) -> list[T]:
    """Deduplicate without changing source order."""
    return list(dict.fromkeys(values))


def money(value: Decimal) -> float:
    return float(value.quantize(TWOPLACES, rounding=ROUND_HALF_UP))


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def variance_hours(later: str | None, earlier: str | None) -> float | None:
    later_dt = parse_timestamp(later)
    earlier_dt = parse_timestamp(earlier)
    if later_dt is None or earlier_dt is None:
        return None
    return round((later_dt - earlier_dt).total_seconds() / 3600, 2)

