"""Contract tests for GET /v1/market/index/latest — AC-A3.1 through AC-A3.3."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from tests.conftest import make_settings, write_dld_csv, write_index_csv


def _client_with_index(client_factory, tmp_path: Path):
    write_dld_csv(
        tmp_path / "Transactions.csv",
        ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-15\n"],
    )
    write_index_csv(
        tmp_path / "index.csv",
        [
            "2026-01-01,1.0,1.0,1.1,1.1,1.2,1.2,0.9,0.9,1.0,1.0,1.1,1.1,0.8,0.8,0.9,0.9,1.0,1.0\n",
            "2026-02-01,1.1,1.1,1.2,1.2,1.3,1.3,1.0,1.0,1.1,1.1,1.2,1.2,0.9,0.9,1.0,1.0,1.1,1.1\n",
        ],
    )
    paths = str(tmp_path / "Transactions.csv")
    settings = make_settings(tmp_path, benchmarks_paths=paths, index_file="index.csv")
    return client_factory(settings)


def test_index_ok_true_shape(client_factory, tmp_path):
    """AC-A3.1: ok=true response has all required fields."""
    client = _client_with_index(client_factory, tmp_path)
    resp = client.get("/v1/market/index/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "date" in body
    assert "segment" in body
    assert "horizon" in body
    assert "index_value" in body
    assert "price_index_value" in body
    assert "dataset_version" in body
    assert "data_state" in body


def test_index_decimal_fields_are_strings(client_factory, tmp_path):
    """Contract: Decimal fields serialised as strings."""
    client = _client_with_index(client_factory, tmp_path)
    body = client.get("/v1/market/index/latest").json()
    if body["index_value"] is not None:
        assert isinstance(body["index_value"], str)
        Decimal(body["index_value"])
    if body["price_index_value"] is not None:
        assert isinstance(body["price_index_value"], str)
        Decimal(body["price_index_value"])


def test_index_latest_date_is_most_recent(client_factory, tmp_path):
    """AC-A3.1: Returns the most recent date row."""
    client = _client_with_index(client_factory, tmp_path)
    body = client.get("/v1/market/index/latest").json()
    assert body["date"] == "2026-02-01"


def test_index_segment_and_horizon_defaults(client_factory, tmp_path):
    """AC-A3.1: Default segment=all, horizon=yearly."""
    client = _client_with_index(client_factory, tmp_path)
    body = client.get("/v1/market/index/latest").json()
    assert body["segment"] == "all"
    assert body["horizon"] == "yearly"


def test_index_segment_flat(client_factory, tmp_path):
    """AC-A3.1: Segment=flat returns flat-specific values."""
    client = _client_with_index(client_factory, tmp_path)
    body = client.get("/v1/market/index/latest?segment=flat&horizon=yearly").json()
    assert body["ok"] is True
    assert body["segment"] == "flat"


def test_index_ok_false_when_no_index_loaded(client_factory, tmp_path):
    """AC-A3.2: No index CSV → ok=false with message, status 200."""
    write_dld_csv(
        tmp_path / "Transactions.csv",
        ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-15\n"],
    )
    paths = str(tmp_path / "Transactions.csv")
    settings = make_settings(tmp_path, benchmarks_paths=paths, index_file="")
    client = client_factory(settings)
    resp = client.get("/v1/market/index/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "message" in body
    assert body["message"]  # non-empty message
    assert body["date"] is None
    assert body["index_value"] is None


def test_index_invalid_segment_returns_422(client_factory, tmp_path):
    """AC-A3.3: Invalid segment → 422 with error shape."""
    settings = make_settings(tmp_path, benchmarks_paths="", index_file="")
    client = client_factory(settings)
    resp = client.get("/v1/market/index/latest?segment=weekly")
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert "details" in body


def test_index_invalid_horizon_returns_422(client_factory, tmp_path):
    """AC-A3.3: Invalid horizon → 422 with error shape."""
    settings = make_settings(tmp_path, benchmarks_paths="", index_file="")
    client = client_factory(settings)
    resp = client.get("/v1/market/index/latest?horizon=decadal")
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert "details" in body


def test_index_openapi_route_present(client_factory, tmp_path):
    """Contract: /v1/market/index/latest registered in OpenAPI."""
    settings = make_settings(tmp_path, benchmarks_paths="", index_file="")
    client = client_factory(settings)
    schema = client.get("/openapi.json").json()
    assert "/v1/market/index/latest" in schema.get("paths", {})
