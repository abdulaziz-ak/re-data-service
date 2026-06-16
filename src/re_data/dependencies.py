from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from re_data.cache import MarketResponseCache
from re_data.config import Settings, get_settings
from re_data.store.dataset_store import DatasetStore


def get_store(request: Request) -> DatasetStore:
    store: DatasetStore = request.app.state.dataset_store
    return store


def get_market_cache(request: Request) -> MarketResponseCache:
    cache: MarketResponseCache = request.app.state.market_cache
    return cache


SettingsDep = Annotated[Settings, Depends(get_settings)]
StoreDep = Annotated[DatasetStore, Depends(get_store)]
MarketCacheDep = Annotated[MarketResponseCache, Depends(get_market_cache)]
