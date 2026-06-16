from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SkipReasonsResponse(BaseModel):
    filtered_procedure: int = 0
    out_of_bounds_ppsf: int = 0
    unparseable: int = 0


class FileMetadataResponse(BaseModel):
    path: str
    name: str
    status: Literal["loaded", "missing", "failed", "partial"]
    detected_schema: (
        Literal[
            "dld_transactions",
            "recent_transactions",
            "generic_comps",
            "residential_sale_index",
            "unknown",
        ]
        | None
    ) = Field(default=None, serialization_alias="schema")
    content_hash: str | None = None
    size_bytes: int | None = None
    rows_read: int = 0
    rows_accepted: int = 0
    rows_skipped: int = 0
    skip_reasons: SkipReasonsResponse = Field(default_factory=SkipReasonsResponse)
    duplicate_content_hash_of: str | None = None


class TotalsResponse(BaseModel):
    accepted_transaction_rows: int = 0
    index_loaded: bool = False
    index_snapshot_count: int = 0
    latest_transaction_date: str | None = None


class DuplicateHashGroupResponse(BaseModel):
    content_hash: str
    paths: list[str]


class DatasetMetadataResponse(BaseModel):
    version: str
    ingested_at: str
    state: Literal["complete", "degraded"]
    files: list[FileMetadataResponse]
    totals: TotalsResponse
    duplicate_content_hashes: list[DuplicateHashGroupResponse]


class HealthResponse(BaseModel):
    ok: bool
    service: str = "re-data-service"
    env: str
    data_state: Literal["complete", "degraded"]
    dataset_version: str | None = None
    ingested_at: str | None = None


class ErrorResponse(BaseModel):
    error: str
    details: list[str]
