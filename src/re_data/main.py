from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from re_data.cache import create_market_cache
from re_data.config import Settings, get_settings
from re_data.routers import admin, dataset, health, market
from re_data.store.dataset_store import DatasetStore

load_dotenv()


def _fmt_validation_errors(exc: RequestValidationError) -> list[str]:
    msgs: list[str] = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x not in ("body",)]
        field = ".".join(loc) if loc else "input"
        msg = err.get("msg", "Invalid value")
        msgs.append(f"{field}: {msg}")
    return msgs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    store = DatasetStore(settings)
    store.initial_load()
    app.state.dataset_store = store
    app.state.settings = settings
    app.state.market_cache = create_market_cache(settings)
    yield
    app.state.market_cache.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Dubai/UAE Real Estate Data Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "Please check the highlighted inputs.",
                "details": _fmt_validation_errors(exc),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, str):
            details = [exc.detail]
            error = exc.detail
        elif isinstance(exc.detail, list):
            details = [str(d) for d in exc.detail]
            error = details[0] if details else "Request failed"
        else:
            error = "Request failed"
            details = [str(exc.detail)]
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": error, "details": details},
        )

    @app.exception_handler(404)
    async def not_found_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": "Not found", "details": ["The requested resource does not exist"]},
        )

    app.include_router(health.router)
    app.include_router(dataset.router)
    app.include_router(admin.router)
    app.include_router(market.router)

    @app.get("/")
    def root(settings: Settings = get_settings()) -> dict[str, Any]:
        return {
            "message": "Dubai/UAE Real Estate Data Service",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/health",
            "env": settings.app_env,
        }

    return app


app = create_app()
