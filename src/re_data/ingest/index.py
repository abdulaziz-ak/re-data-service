from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from re_data.ingest.parsers import norm, parse_date_any, parse_decimal
from re_data.models.domain import IndexKey, IndexSnapshot, SkipReasons


@dataclass
class IndexIngestResult:
    index: dict[IndexKey, IndexSnapshot] = field(default_factory=dict)
    rows_read: int = 0
    rows_accepted: int = 0
    skip_reasons: SkipReasons = field(default_factory=SkipReasons)


def load_residential_sale_index(path: Path) -> IndexIngestResult:
    """Latest row per (segment, horizon) — mirrors benchmarks.py."""
    result = IndexIngestResult()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result.rows_read += 1
            d = parse_date_any(row.get("first_date_of_month"))
            if not d:
                result.skip_reasons = SkipReasons(
                    unparseable=result.skip_reasons.unparseable + 1,
                )
                continue

            accepted_any = False
            for segment in ("all", "flat", "villa"):
                for horizon in ("monthly", "quarterly", "yearly"):
                    idx_col = f"{segment}_{horizon}_index"
                    pidx_col = f"{segment}_{horizon}_price_index"
                    idx_val = parse_decimal(row.get(idx_col))
                    pidx_val = parse_decimal(row.get(pidx_col))
                    snap = IndexSnapshot(
                        date=d,
                        segment=segment,
                        horizon=horizon,
                        index_value=idx_val,
                        price_index_value=pidx_val,
                    )
                    k: IndexKey = (norm(segment), norm(horizon))
                    prev = result.index.get(k)
                    if prev is None or d > prev.date:
                        result.index[k] = snap
                        accepted_any = True
            if accepted_any:
                result.rows_accepted += 1
    return result
