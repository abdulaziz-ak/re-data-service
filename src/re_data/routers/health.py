from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from re_data.dependencies import SettingsDep, StoreDep
from re_data.models.api import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(store: StoreDep, settings: SettingsDep) -> JSONResponse:
    snapshot = store.get_active()
    if snapshot is None:
        body = HealthResponse(
            ok=False,
            env=settings.app_env,
            data_state="degraded",
            dataset_version=None,
            ingested_at=None,
        )
        return JSONResponse(status_code=503, content=body.model_dump())

    body = HealthResponse(
        ok=snapshot.state == "complete",
        env=settings.app_env,
        data_state=snapshot.state,
        dataset_version=snapshot.version if snapshot.state == "complete" else None,
        ingested_at=snapshot.ingested_at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    )
    status_code = 200 if snapshot.state == "complete" else 503
    return JSONResponse(status_code=status_code, content=body.model_dump())
