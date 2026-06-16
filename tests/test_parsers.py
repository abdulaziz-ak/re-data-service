from __future__ import annotations

from decimal import Decimal

from re_data.ingest.parsers import (
    date_from_filename,
    key_tuple,
    norm,
    parse_date_any,
    parse_decimal,
    parse_int,
)


def test_norm_strips_and_lowercases():
    assert norm("  Dubai Marina  ") == "dubai marina"


def test_parse_decimal_handles_commas():
    assert parse_decimal("1,076,391") == Decimal("1076391")


def test_parse_int_extracts_leading_digits():
    assert parse_int("2 BR") == 2


def test_parse_date_any_iso():
    assert parse_date_any("2026-02-23") == "2026-02-23"


def test_date_from_filename():
    assert date_from_filename("transactions-2026-02-23.csv") == "2026-02-23"


def test_key_tuple_defaults():
    assert key_tuple(None, "Marina", None, "flat", 2) == (
        "dubai",
        "marina",
        "",
        "flat",
        2,
    )
