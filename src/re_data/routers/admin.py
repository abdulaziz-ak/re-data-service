from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from re_data.dependencies import StoreDep
from re_data.models.api import DatasetMetadataResponse, ErrorResponse
from re_data.routers.dataset import snapshot_to_response
from re_data.store.dataset_store import ReloadInProgressError

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.post(
    "/reload",
    response_model=DatasetMetadataResponse,
    responses={409: {"model": ErrorResponse}},
)
async def reload_dataset(store: StoreDep) -> DatasetMetadataResponse | JSONResponse:
    try:
        snapshot = await store.reload()
    except ReloadInProgressError:
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                error="Reload already in progress",
                details=["retry after the current ingest completes"],
            ).model_dump(),
        )
    return snapshot_to_response(snapshot)
