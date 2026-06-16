from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Literal

from re_data.config import SQM_TO_SQFT, Settings
from re_data.ingest.parsers import (
    date_from_filename,
    key_tuple,
    norm,
    parse_date_any,
    parse_decimal,
    parse_int,
)
from re_data.models.domain import BenchmarkKey, DetectedSchema, SkipReasons

SkipKind = Literal["filtered_procedure", "out_of_bounds_ppsf", "unparseable", "accepted"]


@dataclass
class IngestAccumulator:
    grouped: dict[BenchmarkKey, list[Decimal]] = field(default_factory=dict)
    last_dates: dict[BenchmarkKey, str] = field(default_factory=dict)
    rows_read: int = 0
    rows_accepted: int = 0
    skip_reasons: SkipReasons = field(default_factory=SkipReasons)
    detected_schema: DetectedSchema = "unknown"

    @property
    def rows_skipped(self) -> int:
        return self.skip_reasons.rows_skipped


def file_content_hash(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size_bytes = 0
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
            size_bytes += len(chunk)
    return digest.hexdigest(), size_bytes


def _record_skip(acc: IngestAccumulator, kind: SkipKind) -> None:
    if kind == "filtered_procedure":
        acc.skip_reasons = SkipReasons(
            filtered_procedure=acc.skip_reasons.filtered_procedure + 1,
            out_of_bounds_ppsf=acc.skip_reasons.out_of_bounds_ppsf,
            unparseable=acc.skip_reasons.unparseable,
        )
    elif kind == "out_of_bounds_ppsf":
        acc.skip_reasons = SkipReasons(
            filtered_procedure=acc.skip_reasons.filtered_procedure,
            out_of_bounds_ppsf=acc.skip_reasons.out_of_bounds_ppsf + 1,
            unparseable=acc.skip_reasons.unparseable,
        )
    elif kind == "unparseable":
        acc.skip_reasons = SkipReasons(
            filtered_procedure=acc.skip_reasons.filtered_procedure,
            out_of_bounds_ppsf=acc.skip_reasons.out_of_bounds_ppsf,
            unparseable=acc.skip_reasons.unparseable + 1,
        )


def _accept_row(
    acc: IngestAccumulator,
    *,
    emirate: str,
    area: str,
    building: str,
    unit_type: str,
    bedrooms: int,
    ppsf: Decimal,
    row_date: str | None,
) -> None:
    k = key_tuple(emirate, area, building, unit_type, bedrooms)
    acc.grouped.setdefault(k, []).append(ppsf)
    if row_date:
        prev = acc.last_dates.get(k)
        if prev is None or row_date > prev:
            acc.last_dates[k] = row_date
    acc.rows_accepted += 1


def _ingest_row_dld_transactions(
    row: dict[str, str],
    acc: IngestAccumulator,
    settings: Settings,
) -> None:
    trans_group = norm(row.get("trans_group_en") or "")
    proc_en = norm(row.get("procedure_name_en") or "")
    if "mortgage" in proc_en or "mortgage" in trans_group:
        _record_skip(acc, "filtered_procedure")
        return
    if "gift" in proc_en or "inherit" in proc_en:
        _record_skip(acc, "filtered_procedure")
        return

    include = (
        ("sale" in trans_group)
        or ("sale" in proc_en)
        or ("sell" in proc_en)
        or ("transfer" in proc_en)
    )
    if not include:
        _record_skip(acc, "filtered_procedure")
        return

    area = row.get("area_name_en") or ""
    if not area:
        _record_skip(acc, "unparseable")
        return

    building = row.get("building_name_en") or ""
    unit_type = row.get("property_sub_type_en") or row.get("property_type_en") or ""
    bedrooms = parse_int(row.get("rooms_en") or row.get("rooms_ar"))

    price = parse_decimal(row.get("actual_worth"))
    area_sqm = parse_decimal(row.get("procedure_area"))
    if price is None or area_sqm is None or area_sqm <= 0:
        _record_skip(acc, "unparseable")
        return

    unit = settings.dld_area_unit
    sqft = area_sqm if unit == "sqft" else area_sqm * SQM_TO_SQFT
    if sqft <= 0:
        _record_skip(acc, "unparseable")
        return

    ppsf = price / sqft
    if ppsf < settings.ppsf_min or ppsf > settings.ppsf_max:
        _record_skip(acc, "out_of_bounds_ppsf")
        return

    d = parse_date_any(row.get("instance_date"))
    _accept_row(
        acc,
        emirate="dubai",
        area=area,
        building=building,
        unit_type=unit_type,
        bedrooms=bedrooms,
        ppsf=ppsf,
        row_date=d,
    )


def _ingest_row_recent_transactions(
    row: dict[str, str],
    acc: IngestAccumulator,
    settings: Settings,
    default_date: str | None,
) -> None:
    proc = norm(row.get("PROCEDURE_EN") or "")
    if "mortgage" in proc or "gift" in proc or "inherit" in proc:
        _record_skip(acc, "filtered_procedure")
        return
    if not ("sale" in proc or "sell" in proc or "transfer" in proc):
        _record_skip(acc, "filtered_procedure")
        return

    area = row.get("AREA_EN") or ""
    if not area:
        _record_skip(acc, "unparseable")
        return

    unit_type = row.get("PROP_SB_TYPE_EN") or row.get("PROP_TYPE_EN") or ""
    bedrooms = parse_int(row.get("ROOMS_EN"))

    price = parse_decimal(row.get("TRANS_VALUE"))
    area_sqm = parse_decimal(row.get("PROCEDURE_AREA") or row.get("ACTUAL_AREA"))
    if price is None or area_sqm is None or area_sqm <= 0:
        _record_skip(acc, "unparseable")
        return

    unit = settings.dld_area_unit
    sqft = area_sqm if unit == "sqft" else area_sqm * SQM_TO_SQFT
    ppsf = price / sqft

    if ppsf < settings.ppsf_min or ppsf > settings.ppsf_max:
        _record_skip(acc, "out_of_bounds_ppsf")
        return

    _accept_row(
        acc,
        emirate="dubai",
        area=area,
        building="",
        unit_type=unit_type,
        bedrooms=bedrooms,
        ppsf=ppsf,
        row_date=default_date,
    )


def _ingest_row_generic(row: dict[str, str], acc: IngestAccumulator, settings: Settings) -> None:
    area = row.get("area") or row.get("Area")
    if not area:
        _record_skip(acc, "unparseable")
        return

    emirate = row.get("emirate") or row.get("Emirate") or "dubai"
    building = row.get("building") or row.get("Building") or ""
    unit_type = row.get("unit_type") or row.get("UnitType") or row.get("unit") or ""
    bedrooms = parse_int(row.get("bedrooms") or row.get("Bedrooms"))

    price = parse_decimal(row.get("price_aed") or row.get("Price") or row.get("price"))
    sqft = parse_decimal(
        row.get("size_sqft") or row.get("sqft") or row.get("Size") or row.get("area_sqft")
    )
    if price is None or sqft is None or sqft <= 0:
        _record_skip(acc, "unparseable")
        return

    ppsf = price / sqft
    if ppsf < settings.ppsf_min or ppsf > settings.ppsf_max:
        _record_skip(acc, "out_of_bounds_ppsf")
        return

    d = parse_date_any(row.get("date") or row.get("Date"))
    _accept_row(
        acc,
        emirate=emirate,
        area=area,
        building=building,
        unit_type=unit_type,
        bedrooms=bedrooms,
        ppsf=ppsf,
        row_date=d,
    )


def ingest_csv_file(path: Path, settings: Settings) -> IngestAccumulator:
    acc = IngestAccumulator()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = set(h or "" for h in (reader.fieldnames or []))

        is_dld = "transaction_id" in headers
        has_worth = "actual_worth" in headers or "meter_sale_price" in headers
        if is_dld and has_worth:
            acc.detected_schema = "dld_transactions"
            for row in reader:
                acc.rows_read += 1
                _ingest_row_dld_transactions(row, acc, settings)
            return acc

        if "PROCEDURE_EN" in headers and "TRANS_VALUE" in headers and "AREA_EN" in headers:
            acc.detected_schema = "recent_transactions"
            default_date = date_from_filename(path.name)
            for row in reader:
                acc.rows_read += 1
                _ingest_row_recent_transactions(row, acc, settings, default_date)
            return acc

        acc.detected_schema = "generic_comps"
        for row in reader:
            acc.rows_read += 1
            _ingest_row_generic(row, acc, settings)
    return acc


def merge_accumulator(
    target_grouped: dict[BenchmarkKey, list[Decimal]],
    target_dates: dict[BenchmarkKey, str],
    acc: IngestAccumulator,
) -> None:
    for k, values in acc.grouped.items():
        target_grouped.setdefault(k, []).extend(values)
    for k, d in acc.last_dates.items():
        prev = target_dates.get(k)
        if prev is None or d > prev:
            target_dates[k] = d
