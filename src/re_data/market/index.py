"""Market index lookup — latest snapshot for a given segment/horizon pair."""

from __future__ import annotations

from re_data.ingest.parsers import norm
from re_data.models.domain import DatasetSnapshot, IndexSnapshot


def latest_index(
    snapshot: DatasetSnapshot,
    *,
    segment: str,
    horizon: str,
) -> IndexSnapshot | None:
    """Return the latest IndexSnapshot for *segment*/*horizon*, or None if absent.

    Mirrors BenchmarksStore.latest_index from benchmarks.py.
    """
    return snapshot.index.get((norm(segment), norm(horizon)))
