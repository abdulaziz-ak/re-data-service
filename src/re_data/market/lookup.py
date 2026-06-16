"""PPSF lookup with progressive-relaxation fallback chain.

Stats (_median, _calc_stat) and the key-expansion chain are copied from
realestate-core-service/benchmarks.py so that parity tests can assert
identical median/confidence values on shared CSV fixtures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from re_data.ingest.parsers import key_tuple, norm
from re_data.market.aliases import _AREA_ALIASES, _UNIT_TYPE_ALIASES
from re_data.models.domain import BenchmarkKey, BenchmarkStat, DatasetSnapshot


@dataclass(frozen=True)
class StatResult:
    median: Decimal
    n: int
    confidence: float


@dataclass(frozen=True)
class PpsfLookupResult:
    stat: BenchmarkStat
    matched_key: BenchmarkKey


def _median(vals: list[Decimal]) -> Decimal:
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return Decimal("0")
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / Decimal("2")


def _calc_stat(vals: tuple[Decimal, ...] | list[Decimal]) -> StatResult:
    """Compute trimmed median and confidence, mirroring benchmarks.py._calc_stat."""
    n = len(vals)
    if n == 0:
        return StatResult(median=Decimal("0"), n=0, confidence=0.0)

    s = sorted(vals)
    if n >= 10:
        k = int(n * 0.10)
        s2 = s[k : n - k] if (n - 2 * k) >= 1 else s
    else:
        s2 = s

    med = _median(s2)
    conf = float(min(1.0, math.log(max(n, 1) + 1) / math.log(101)))
    return StatResult(median=med, n=n, confidence=conf)


def lookup_ppsf(
    snapshot: DatasetSnapshot,
    *,
    emirate: str | None,
    area: str | None,
    building: str | None,
    unit_type: str | None,
    bedrooms: int | None,
) -> PpsfLookupResult | None:
    """Look up PPSF for the given parameters using a progressive-relaxation chain.

    Mirrors BenchmarksStore.lookup_stat from benchmarks.py, operating on the
    snapshot's raw transaction tuples instead of a pre-computed BenchmarkStat dict.
    Stats (median, confidence) are computed on demand from the stored ppsf values.
    """
    ut_norm = norm(unit_type or "")
    ut_candidates = list(
        dict.fromkeys(
            _UNIT_TYPE_ALIASES.get(ut_norm, [ut_norm] if ut_norm else []) + [""]
        )
    )

    area_norm = norm(area or "")
    area_expanded = _AREA_ALIASES.get(area_norm, area_norm)
    area_candidates = list(dict.fromkeys([area_expanded, area_norm, ""]))

    candidates: list[BenchmarkKey] = []
    for ar in area_candidates:
        for ut in ut_candidates:
            candidates += [
                key_tuple(emirate, ar, building, ut, bedrooms),
                key_tuple(emirate, ar, "", ut, bedrooms),
                key_tuple(emirate, ar, "", ut, 0),
            ]
    candidates.append(key_tuple(emirate, "", "", "", 0))

    seen: set[BenchmarkKey] = set()
    for ck in candidates:
        if ck in seen:
            continue
        seen.add(ck)
        values = snapshot.transactions.get(ck)
        if values:
            result = _calc_stat(values)
            stat = BenchmarkStat(
                aed_per_sqft=result.median,
                sample_size=result.n,
                last_updated=snapshot.last_dates.get(ck),
                source="csv",
                confidence=result.confidence,
            )
            return PpsfLookupResult(stat=stat, matched_key=ck)

    return None
