"""Contract tests for GET /v1/market/areas — AC-A1.1 through AC-A1.4."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import make_settings, write_dld_csv, write_index_csv


def _client_with_jvc_data(client_factory, tmp_path: Path):
    """Fixture-level helper: one JVC row so the snapshot is complete."""
    write_dld_csv(
        tmp_path / "Transactions.csv",
        [
            "1,2000000,100,Jumeirah Village Circle,,flat,1,Sales,Sale,2026-01-15\n",
            "2,2200000,105,Al Marjan Island,,flat,2,Sales,Sale,2026-01-10\n",
        ],
    )
    write_index_csv(
        tmp_path / "index.csv",
        ["2026-02-01,1,1,1,1,1.2,1.2,1,1,1,1,1,1,1,1,1,1,1,1\n"],
    )
    paths = str(tmp_path / "Transactions.csv")
    settings = make_settings(tmp_path, benchmarks_paths=paths, index_file="index.csv")
    return client_factory(settings)


def test_areas_200_shape_with_items_and_provenance(client_factory, tmp_path):
    """AC-A1.1: Response includes items list, dataset_version, data_state."""
    client = _client_with_jvc_data(client_factory, tmp_path)
    resp = client.get("/v1/market/areas")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "dataset_version" in body
    assert "data_state" in body
    assert body["data_state"] in ("complete", "degraded")
    assert len(body["dataset_version"]) == 64  # sha256 hex


def test_areas_items_have_correct_fields(client_factory, tmp_path):
    """AC-A1.1: Each item has value, label, emirate."""
    client = _client_with_jvc_data(client_factory, tmp_path)
    resp = client.get("/v1/market/areas")
    body = resp.json()
    assert len(body["items"]) > 0
    for item in body["items"]:
        assert "value" in item
        assert "label" in item
        assert "emirate" in item
        assert isinstance(item["value"], str)
        assert isinstance(item["label"], str)
        assert isinstance(item["emirate"], str)


def test_areas_sorted_by_label(client_factory, tmp_path):
    """AC-A1.1: Items sorted by label ascending."""
    client = _client_with_jvc_data(client_factory, tmp_path)
    body = client.get("/v1/market/areas").json()
    labels = [i["label"] for i in body["items"]]
    assert labels == sorted(labels)


def test_areas_jvc_alias_value(client_factory, tmp_path):
    """AC-A1.1: JVC canonical area gets 'jvc' as value (longest alias key)."""
    client = _client_with_jvc_data(client_factory, tmp_path)
    body = client.get("/v1/market/areas").json()
    jvc_item = next((i for i in body["items"] if "jumeirah village circle" in i["label"].lower()), None)
    assert jvc_item is not None
    assert jvc_item["value"] == "jvc"
    assert jvc_item["emirate"] == "dubai"


def test_areas_emirate_filter_rak(client_factory, tmp_path):
    """AC-A1.2: Emirate filter returns only matching areas."""
    client = _client_with_jvc_data(client_factory, tmp_path)
    body = client.get("/v1/market/areas?emirate=ras+al+khaimah").json()
    assert all(i["emirate"] == "ras al khaimah" for i in body["items"])
    # Al Marjan Island is in RAK
    assert any("marjan" in i["label"].lower() for i in body["items"])


def test_areas_emirate_filter_case_insensitive(client_factory, tmp_path):
    """AC-A1.2: Emirate filter is case-insensitive."""
    client = _client_with_jvc_data(client_factory, tmp_path)
    body_lower = client.get("/v1/market/areas?emirate=dubai").json()
    body_upper = client.get("/v1/market/areas?emirate=DUBAI").json()
    assert body_lower["items"] == body_upper["items"]


def test_areas_degraded_snapshot_returns_200(client_factory, tmp_path):
    """AC-A1.3 + AC-A1.4: Degraded snapshot → 200 with data_state degraded."""
    settings = make_settings(tmp_path, benchmarks_paths="", index_file="")
    client = client_factory(settings)
    resp = client.get("/v1/market/areas")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_state"] == "degraded"
    assert body["items"] == []


def test_areas_openapi_route_present(client_factory, tmp_path):
    """Contract: /v1/market/areas is registered in OpenAPI schema."""
    settings = make_settings(tmp_path, benchmarks_paths="", index_file="")
    client = client_factory(settings)
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert "/v1/market/areas" in paths
    assert "get" in paths["/v1/market/areas"]


def test_no_comps_stub_in_openapi(client_factory, tmp_path):
    """Q6: /v1/market/comps must NOT exist (deferred to ST-005)."""
    settings = make_settings(tmp_path, benchmarks_paths="", index_file="")
    client = client_factory(settings)
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert "/v1/market/comps" not in paths
