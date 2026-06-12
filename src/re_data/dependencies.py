from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from re_data.config import Settings, get_settings
from re_data.store.dataset_store import DatasetStore


def get_store(request: Request) -> DatasetStore:
    store: DatasetStore = request.app.state.dataset_store
    return store


SettingsDep = Annotated[Settings, Depends(get_settings)]
StoreDep = Annotated[DatasetStore, Depends(get_store)]
