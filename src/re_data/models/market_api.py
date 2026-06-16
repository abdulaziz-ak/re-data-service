"""Pydantic response models for the /v1/market/* endpoints.

All Decimal money fields are serialised as strings per the engineering contract.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_serializer


class MatchedKey(BaseModel):
    emirate: str
    area: str
    building: str
    unit_type: str
    bedrooms: int


class AreaItem(BaseModel):
    value: str
    label: str
    emirate: str


class AreasListResponse(BaseModel):
    items: list[AreaItem]
    dataset_version: str
    data_state: Literal["complete", "degraded"]


class PpsfResponse(BaseModel):
    found: bool
    aed_per_sqft: Decimal | None = None
    sample_size: int = 0
    confidence: float | None = None
    last_updated: str | None = None
    source: str | None = None
    matched_key: MatchedKey | None = None
    dataset_version: str
    data_state: Literal["complete", "degraded"]

    @field_serializer("aed_per_sqft")
    def _ser_aed(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None


class IndexLatestResponse(BaseModel):
    ok: bool
    date: str | None = None
    segment: str | None = None
    horizon: str | None = None
    index_value: Decimal | None = None
    price_index_value: Decimal | None = None
    message: str | None = None
    dataset_version: str
    data_state: Literal["complete", "degraded"]

    @field_serializer("index_value", "price_index_value")
    def _ser_decimal(self, v: Decimal | None) -> str | None:
        return str(v) if v is not None else None
