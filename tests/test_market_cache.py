from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from re_data.cache import NullMarketResponseCache
from re_data.models.market_api import AreaItem, AreasListResponse
from tests.conftest import make_settings, write_dld_csv, write_index_csv


class FakeMarketCache:
    def __init__(self, cached: BaseModel | None = None) -> None:
        self.cached = cached
        self.keys: list[tuple[str, str, dict[str, object]]] = []
        self.sets: list[tuple[str, BaseModel]] = []

    def build_key(self, endpoint: str, dataset_version: str, params: dict[str, object]) -> str:
        self.keys.append((endpoint, dataset_version, params))
        return f"{endpoint}:{dataset_version}:{params}"

    def get_model(self, key: str, model_type: type[Any]) -> Any | None:
        return self.cached

    def set_model(self, key: str, value: BaseModel) -> None:
        self.sets.append((key, value))

    def close(self) -> None:
        return None


def _client_with_area_data(client_factory, tmp_path: Path):
    write_dld_csv(
        tmp_path / "Transactions.csv",
        ["1,2000000,100,Dubai Marina,,flat,1,Sales,Sale,2026-01-15\n"],
    )
    write_index_csv(
        tmp_path / "index.csv",
        ["2026-02-01,1,1,1,1,1.2,1.2,1,1,1,1,1,1,1,1,1,1,1,1\n"],
    )
    settings = make_settings(
        tmp_path,
        benchmarks_paths=str(tmp_path / "Transactions.csv"),
        index_file="index.csv",
    )
    return client_factory(settings)


def test_null_market_cache_is_noop():
    cache = NullMarketResponseCache()
    key = cache.build_key("areas", "v1", {"emirate": "dubai"})
    assert key == ""
    assert cache.get_model(key, AreasListResponse) is None


def test_areas_route_returns_cached_response(client_factory, tmp_path):
    client = _client_with_area_data(client_factory, tmp_path)
    cached = AreasListResponse(
        items=[AreaItem(value="cached", label="Cached Area", emirate="dubai")],
        dataset_version="cached-version",
        data_state="complete",
    )
    fake_cache = FakeMarketCache(cached=cached)
    client.app.state.market_cache = fake_cache

    body = client.get("/v1/market/areas").json()

    assert body["items"] == [{"value": "cached", "label": "Cached Area", "emirate": "dubai"}]
    assert body["dataset_version"] == "cached-version"
    assert fake_cache.sets == []


def test_areas_route_caches_uncached_response(client_factory, tmp_path):
    client = _client_with_area_data(client_factory, tmp_path)
    fake_cache = FakeMarketCache()
    client.app.state.market_cache = fake_cache

    body = client.get("/v1/market/areas").json()

    assert body["items"]
    assert len(fake_cache.sets) == 1
    _, cached_response = fake_cache.sets[0]
    assert isinstance(cached_response, AreasListResponse)
    assert len(cached_response.dataset_version) == 64
