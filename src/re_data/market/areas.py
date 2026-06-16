"""Area listing — derives dropdown options from the active DatasetSnapshot transactions.

Only areas backed by at least one accepted transaction row are included.
This is an intentional improvement over the static alias-only list in benchmarks.py
(see DESIGN-ST-002-ST-004 §2 requirement tension flag).
"""

from __future__ import annotations

from re_data.market.aliases import (
    _AREA_EMIRATE_MAP,
    resolve_area_value,
)
from re_data.models.domain import DatasetSnapshot, DataState


def list_areas(
    snapshot: DatasetSnapshot,
    *,
    emirate: str | None = None,
) -> tuple[list[dict[str, str]], DataState]:
    """Return area items and effective data_state from *snapshot*.

    Each item: ``{"value": "<best alias key>", "label": "<Title Case>",
    "emirate": "<emirate>"}`` sorted by label.

    When *emirate* is given (already normalised by caller), only areas belonging
    to that emirate are included.

    Returns degraded state when the snapshot has no transactions regardless of
    the snapshot's own recorded state, since an empty area list is always
    misleading to callers.
    """
    if not snapshot.transactions:
        return [], "degraded"

    # Collect unique normalised canonical area strings from ingest keys (index 1).
    canonical_areas: set[str] = set()
    for key in snapshot.transactions:
        area = key[1]
        if area:
            canonical_areas.add(area)

    items: list[dict[str, str]] = []
    for canonical in canonical_areas:
        area_emirate = _AREA_EMIRATE_MAP.get(canonical, "dubai")
        if emirate and area_emirate != emirate:
            continue
        items.append(
            {
                "value": resolve_area_value(canonical),
                "label": canonical.title(),
                "emirate": area_emirate,
            }
        )

    items.sort(key=lambda o: o["label"])
    return items, snapshot.state
