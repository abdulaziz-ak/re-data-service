from __future__ import annotations

from fastapi import APIRouter, HTTPException

from re_data.dependencies import StoreDep
from re_data.models.api import (
    DatasetMetadataResponse,
    DuplicateHashGroupResponse,
    FileMetadataResponse,
    SkipReasonsResponse,
    TotalsResponse,
)
from re_data.models.domain import DatasetSnapshot

router = APIRouter(prefix="/v1", tags=["dataset"])


def snapshot_to_response(snapshot: DatasetSnapshot) -> DatasetMetadataResponse:
    return DatasetMetadataResponse(
        version=snapshot.version,
        ingested_at=snapshot.ingested_at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        state=snapshot.state,
        files=[
            FileMetadataResponse(
                path=f.path,
                name=f.name,
                status=f.status,
                detected_schema=f.schema,
                content_hash=f.content_hash,
                size_bytes=f.size_bytes,
                rows_read=f.rows_read,
                rows_accepted=f.rows_accepted,
                rows_skipped=f.rows_skipped,
                skip_reasons=SkipReasonsResponse(
                    filtered_procedure=f.skip_reasons.filtered_procedure,
                    out_of_bounds_ppsf=f.skip_reasons.out_of_bounds_ppsf,
                    unparseable=f.skip_reasons.unparseable,
                ),
                duplicate_content_hash_of=f.duplicate_content_hash_of,
            )
            for f in snapshot.files
        ],
        totals=TotalsResponse(
            accepted_transaction_rows=snapshot.totals.accepted_transaction_rows,
            index_loaded=snapshot.totals.index_loaded,
            index_snapshot_count=snapshot.totals.index_snapshot_count,
            latest_transaction_date=snapshot.totals.latest_transaction_date,
        ),
        duplicate_content_hashes=[
            DuplicateHashGroupResponse(content_hash=g.content_hash, paths=list(g.paths))
            for g in snapshot.duplicate_content_hashes
        ],
    )


@router.get("/dataset", response_model=DatasetMetadataResponse)
def get_dataset(store: StoreDep) -> DatasetMetadataResponse:
    snapshot = store.get_active()
    if snapshot is None:
        raise HTTPException(status_code=503, detail="Dataset not loaded")
    return snapshot_to_response(snapshot)
