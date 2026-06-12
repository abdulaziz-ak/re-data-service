"""Market read API — /v1/market/areas, /v1/market/ppsf, /v1/market/index/latest."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from re_data.dependencies import StoreDep
from re_data.market.aliases import _norm
from re_data.market.areas import list_areas
from re_data.market.index import latest_index
from re_data.market.lookup import lookup_ppsf
from re_data.models.market_api import (
    AreaItem,
    AreasListResponse,
    IndexLatestResponse,
    MatchedKey,
    PpsfResponse,
)

router = APIRouter(prefix="/v1/market", tags=["market"])

_DEGRADED_VERSION = "none"


@router.get("/areas", response_model=AreasListResponse)
def get_areas(
    emirate: str | None = Query(default=None, description="Filter by emirate (case-insensitive)"),
    store: StoreDep = ...,  # type: ignore[assignment]
) -> AreasListResponse:
    """List all areas derived from the transaction dataset, with alias resolution."""
    snapshot = store.get_active()
    if snapshot is None:
        return AreasListResponse(
            items=[],
            dataset_version=_DEGRADED_VERSION,
            data_state="degraded",
        )

    emirate_norm = _norm(emirate) if emirate else None
    items, data_state = list_areas(snapshot, emirate=emirate_norm)

    return AreasListResponse(
        items=[AreaItem(value=i["value"], label=i["label"], emirate=i["emirate"]) for i in items],
        dataset_version=snapshot.version,
        data_state=data_state,
    )


@router.get("/ppsf", response_model=PpsfResponse)
def get_ppsf(
    emirate: str | None = Query(default=None),
    area: str | None = Query(default=None),
    building: str | None = Query(default=None),
    unit_type: str | None = Query(default=None),
    bedrooms: int | None = Query(default=None, description="0 or omitted means unspecified"),
    store: StoreDep = ...,  # type: ignore[assignment]
) -> PpsfResponse:
    """Look up AED/sqft benchmark with progressive-relaxation fallback."""
    snapshot = store.get_active()
    if snapshot is None:
        return PpsfResponse(
            found=False,
            dataset_version=_DEGRADED_VERSION,
            data_state="degraded",
        )

    result = lookup_ppsf(
        snapshot,
        emirate=emirate,
        area=area,
        building=building,
        unit_type=unit_type,
        bedrooms=int(bedrooms or 0),
    )

    if result is None:
        return PpsfResponse(
            found=False,
            dataset_version=snapshot.version,
            data_state=snapshot.state,
        )

    mk = result.matched_key
    return PpsfResponse(
        found=True,
        aed_per_sqft=result.stat.aed_per_sqft,
        sample_size=result.stat.sample_size,
        confidence=result.stat.confidence,
        last_updated=result.stat.last_updated,
        source=result.stat.source,
        matched_key=MatchedKey(
            emirate=mk[0],
            area=mk[1],
            building=mk[2],
            unit_type=mk[3],
            bedrooms=mk[4],
        ),
        dataset_version=snapshot.version,
        data_state=snapshot.state,
    )


@router.get("/index/latest", response_model=IndexLatestResponse)
def get_index_latest(
    segment: Literal["all", "flat", "villa"] = Query(default="all"),
    horizon: Literal["monthly", "quarterly", "yearly"] = Query(default="yearly"),
    store: StoreDep = ...,  # type: ignore[assignment]
) -> IndexLatestResponse:
    """Return the latest market index snapshot for the given segment and horizon."""
    snapshot = store.get_active()
    if snapshot is None:
        return IndexLatestResponse(
            ok=False,
            message="No index data loaded.",
            dataset_version=_DEGRADED_VERSION,
            data_state="degraded",
        )

    snap = latest_index(snapshot, segment=segment, horizon=horizon)

    if snap is None:
        return IndexLatestResponse(
            ok=False,
            message="No index data loaded.",
            dataset_version=snapshot.version,
            data_state="degraded",
        )

    return IndexLatestResponse(
        ok=True,
        date=snap.date,
        segment=snap.segment,
        horizon=snap.horizon,
        index_value=snap.index_value,
        price_index_value=snap.price_index_value,
        dataset_version=snapshot.version,
        data_state=snapshot.state,
    )
