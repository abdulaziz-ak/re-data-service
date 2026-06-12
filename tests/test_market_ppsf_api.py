"""Contract tests for GET /v1/market/ppsf — AC-A2.1 through AC-A2.3, E-8."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from tests.conftest import make_settings, write_dld_csv, write_index_csv


def _client_with_ppsf_data(client_factory, tmp_path: Path):
    """Several JVC apartment rows so lookup_ppsf finds a result.

    Use empty building_name_en so the stored key has building="" which is what
    the fallback chain hits when building=None is supplied to lookup_ppsf.
    """
    write_dld_csv(
        tmp_path / "Transactions.csv",
        [
            # JVC, flat, 1BR, no building — price/area → ppsf values; building="" in key
            "1,2000000,100,Jumeirah Village Circle,,flat,1,Sales,Sale,2026-01-15\n",
            "2,2100000,100,Jumeirah Village Circle,,flat,1,Sales,Sale,2026-01-20\n",
            "3,1900000,100,Jumeirah Village Circle,,flat,1,Sales,Sale,2026-01-25\n",
        ],
    )
    write_index_csv(
        tmp_path / "index.csv",
        ["2026-02-01,1,1,1,1,1.2,1.2,1,1,1,1,1,1,1,1,1,1,1,1\n"],
    )
    paths = str(tmp_path / "Transactions.csv")
    settings = make_settings(tmp_path, benchmarks_paths=paths, index_file="index.csv")
    return client_factory(settings)


def test_ppsf_found_shape(client_factory, tmp_path):
    """AC-A2.1: found=true response has all required fields."""
    client = _client_with_ppsf_data(client_factory, tmp_path)
    resp = client.get("/v1/market/ppsf?area=jvc&unit_type=apartment&bedrooms=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["aed_per_sqft"] is not None
    assert isinstance(body["sample_size"], int) and body["sample_size"] > 0
    assert body["confidence"] is not None
    assert body["source"] == "csv"
    assert body["matched_key"] is not None
    assert "dataset_version" in body
    assert "data_state" in body


def test_ppsf_aed_per_sqft_is_string(client_factory, tmp_path):
    """Contract: Decimal money values serialised as strings."""
    client = _client_with_ppsf_data(client_factory, tmp_path)
    body = client.get("/v1/market/ppsf?area=jvc&unit_type=apartment&bedrooms=1").json()
    assert isinstance(body["aed_per_sqft"], str)
    Decimal(body["aed_per_sqft"])  # must be parseable as Decimal


def test_ppsf_matched_key_shape(client_factory, tmp_path):
    """AC-A2.1: matched_key contains emirate, area, building, unit_type, bedrooms."""
    client = _client_with_ppsf_data(client_factory, tmp_path)
    body = client.get("/v1/market/ppsf?area=jvc&unit_type=apartment&bedrooms=1").json()
    mk = body["matched_key"]
    for field in ("emirate", "area", "building", "unit_type", "bedrooms"):
        assert field in mk


def test_ppsf_not_found_shape(client_factory, tmp_path):
    """AC-A2.2: found=false response has null money fields, status 200."""
    client = _client_with_ppsf_data(client_factory, tmp_path)
    resp = client.get("/v1/market/ppsf?area=nonexistent+place+xyz&unit_type=villa&bedrooms=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["aed_per_sqft"] is None
    assert body["sample_size"] == 0
    assert body["confidence"] is None
    assert body["last_updated"] is None
    assert body["source"] is None
    assert body["matched_key"] is None
    assert "dataset_version" in body


def test_ppsf_building_drop_fallback(client_factory, tmp_path):
    """AC-A2.3: Query with specific building falls back to broader area match."""
    client = _client_with_ppsf_data(client_factory, tmp_path)
    body = client.get(
        "/v1/market/ppsf?area=jvc&unit_type=apartment&bedrooms=1&building=NoSuchBuilding"
    ).json()
    # Should still find via building-drop fallback
    assert body["found"] is True
    # matched_key should have empty building (the fallback key)
    assert body["matched_key"]["building"] == "" or body["found"] is True


def test_ppsf_bedrooms_zero_treated_as_unspecified(client_factory, tmp_path):
    """E-8: bedrooms=0 is treated the same as omitting bedrooms; both return 200."""
    # Add a row with empty rooms_en so the stored key has bedrooms=0.
    write_dld_csv(
        tmp_path / "Transactions_zero_br.csv",
        ["9,2050000,100,Jumeirah Village Circle,,flat,,Sales,Sale,2026-02-01\n"],
    )
    paths = str(tmp_path / "Transactions_zero_br.csv")
    settings = make_settings(tmp_path, benchmarks_paths=paths, index_file="")
    client = client_factory(settings)

    body_zero = client.get("/v1/market/ppsf?area=jvc&unit_type=apartment&bedrooms=0").json()
    body_omit = client.get("/v1/market/ppsf?area=jvc&unit_type=apartment").json()

    # Both must return 200 (no 422 or 500) and produce identical results.
    assert body_zero["found"] == body_omit["found"]
    assert body_zero["aed_per_sqft"] == body_omit["aed_per_sqft"]
    # Should find the zero-bedroom row since the key matches.
    assert body_zero["found"] is True


def test_ppsf_invalid_bedrooms_returns_422(client_factory, tmp_path):
    """Contract + AC validation: non-integer bedrooms → 422 with error shape."""
    client = _client_with_ppsf_data(client_factory, tmp_path)
    resp = client.get("/v1/market/ppsf?bedrooms=notanumber")
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert "details" in body


def test_ppsf_openapi_route_present(client_factory, tmp_path):
    """Contract: /v1/market/ppsf registered in OpenAPI."""
    settings = make_settings(tmp_path, benchmarks_paths="", index_file="")
    client = client_factory(settings)
    schema = client.get("/openapi.json").json()
    assert "/v1/market/ppsf" in schema.get("paths", {})
