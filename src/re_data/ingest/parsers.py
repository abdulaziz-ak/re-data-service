from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal


def norm(s: str) -> str:
    return (s or "").strip().lower()


def key_tuple(
    emirate: str | None,
    area: str | None,
    building: str | None,
    unit_type: str | None,
    bedrooms: int | None,
) -> tuple[str, str, str, str, int]:
    return (
        norm(emirate or "dubai"),
        norm(area or ""),
        norm(building or ""),
        norm(unit_type or ""),
        int(bedrooms or 0),
    )


def parse_decimal(x: object) -> Decimal | None:
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except Exception:
        return None


def parse_int(x: object) -> int:
    if x is None:
        return 0
    s = str(x).strip()
    if not s:
        return 0
    m = re.match(r"^\s*(\d+)", s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return 0
    try:
        return int(float(s))
    except Exception:
        return 0


def parse_date_any(x: object) -> str | None:
    """Return YYYY-MM-DD if parseable."""
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None

    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass

    try:
        return datetime.fromisoformat(s).date().isoformat()
    except Exception:
        return None


def date_from_filename(name: str) -> str | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    if m:
        return m.group(1)
    return None
