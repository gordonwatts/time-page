"""Shared parsing helpers for user-supplied date expressions."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime, time, timedelta

try:
    import dateparser
except ModuleNotFoundError:  # pragma: no cover - exercised only in minimal envs
    dateparser = None

_RELATIVE_SHORTHAND = re.compile(r"^(?P<sign>[+-])(?P<amount>\d+)(?P<unit>[hdwmy])$")
_UNIT_NAMES = {
    "h": "hour",
    "d": "day",
    "w": "week",
    "m": "month",
    "y": "year",
}
_NATURAL_RELATIVE = re.compile(
    r"^(?:(?P<future>in)\s+)?(?P<amount>\d+)\s+"
    r"(?P<unit>hour|day|week|month|year)s?(?:\s+(?P<past>ago))?$"
)


def current_datetime() -> datetime:
    """Return the current local time."""
    return datetime.now()


def _expand_relative_shorthand(value: str) -> str:
    match = _RELATIVE_SHORTHAND.fullmatch(value)
    if match is None:
        return value

    amount = int(match.group("amount"))
    unit = _UNIT_NAMES[match.group("unit")]
    plural = "" if amount == 1 else "s"
    if match.group("sign") == "-":
        return f"{amount} {unit}{plural} ago"
    return f"in {amount} {unit}{plural}"


def parse_date_expression(
    value: str | date | datetime | None,
    *,
    label: str,
    relative_base: datetime | date | None = None,
) -> date | None:
    """Parse an ISO date, shorthand offset, or natural-language date expression."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(
            f"{label} must be a valid date expression like 2025-03-20, now, or -3d."
        )

    text = value.strip()
    if not text:
        raise ValueError(
            f"{label} must be a valid date expression like 2025-03-20, now, or -3d."
        )

    try:
        return date.fromisoformat(text)
    except ValueError:
        pass

    base = relative_base or current_datetime()
    if isinstance(base, date) and not isinstance(base, datetime):
        base = datetime.combine(base, time.min)

    expression = _expand_relative_shorthand(text)
    parsed = _parse_with_dateparser(expression, base) or _parse_without_dateparser(
        expression, base
    )
    if parsed is None:
        raise ValueError(
            f"{label} must be a valid date expression like 2025-03-20, now, or -3d."
        )
    return parsed.date()


def _parse_with_dateparser(
    expression: str, relative_base: datetime
) -> datetime | None:
    if dateparser is None:
        return None
    return dateparser.parse(
        expression,
        settings={
            "RELATIVE_BASE": relative_base,
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )


def _parse_without_dateparser(
    expression: str, relative_base: datetime
) -> datetime | None:
    lowered = expression.lower()
    if lowered in {"now", "today"}:
        return relative_base
    if lowered == "yesterday":
        return relative_base - timedelta(days=1)
    if lowered == "tomorrow":
        return relative_base + timedelta(days=1)

    match = _NATURAL_RELATIVE.fullmatch(lowered)
    if match is None:
        return None

    amount = int(match.group("amount"))
    unit = match.group("unit")
    sign = -1 if match.group("past") else 1
    if match.group("future"):
        sign = 1

    if unit == "hour":
        return relative_base + timedelta(hours=sign * amount)
    if unit == "day":
        return relative_base + timedelta(days=sign * amount)
    if unit == "week":
        return relative_base + timedelta(days=sign * amount * 7)
    if unit == "month":
        return _shift_months(relative_base, sign * amount)
    if unit == "year":
        return _shift_months(relative_base, sign * amount * 12)
    return None


def _shift_months(value: datetime, months: int) -> datetime:
    year = value.year + ((value.month - 1 + months) // 12)
    month = ((value.month - 1 + months) % 12) + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
