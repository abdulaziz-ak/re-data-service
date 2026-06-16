from __future__ import annotations

import asyncio

from re_data.config import Settings
from re_data.ingest.runner import run_ingest
from re_data.models.domain import DatasetSnapshot

_DEFAULT_MAX_RELOAD_S: float = 300.0


class ReloadInProgressError(Exception):
    """Raised when a second reload is requested while one is running."""


class ReloadTimeoutError(Exception):
    """Raised when the ingest worker exceeds the configured reload timeout."""


class DatasetStore:
    def __init__(self, settings: Settings, max_reload_s: float = _DEFAULT_MAX_RELOAD_S) -> None:
        self._settings = settings
        self._max_reload_s = max_reload_s
        self._active: DatasetSnapshot | None = None
        self._reload_lock = asyncio.Lock()

    @property
    def reload_in_progress(self) -> bool:
        return self._reload_lock.locked()

    def get_active(self) -> DatasetSnapshot | None:
        return self._active

    def initial_load(self) -> None:
        self._active = run_ingest(self._settings)

    async def reload(self) -> DatasetSnapshot:
        if self._reload_lock.locked():
            raise ReloadInProgressError()
        async with self._reload_lock:
            try:
                staging = await asyncio.wait_for(
                    asyncio.to_thread(run_ingest, self._settings),
                    timeout=self._max_reload_s,
                )
            except asyncio.TimeoutError:
                raise ReloadTimeoutError(
                    f"ingest timed out after {self._max_reload_s}s"
                )
            self._active = staging
            return staging
