from __future__ import annotations

from unittest.mock import patch

from tests.conftest import make_settings


def test_health_complete_200(client_factory, sample_complete_dataset):
    client = client_factory(sample_complete_dataset)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["service"] == "re-data-service"
    assert body["data_state"] == "complete"
    assert len(body["dataset_version"]) == 64
    assert body["ingested_at"] is not None


def test_health_degraded_503(client_factory, tmp_path):
    settings = make_settings(
        tmp_path,
        benchmarks_paths=str(tmp_path / "missing.csv"),
        index_file="",
    )
    client = client_factory(settings)
    resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["data_state"] == "degraded"
    assert body["dataset_version"] is None


def test_health_does_not_open_csv_files(client_factory, sample_complete_dataset):
    client = client_factory(sample_complete_dataset)
    with patch("pathlib.Path.open") as mock_open:
        resp = client.get("/health")
        mock_open.assert_not_called()
    assert resp.status_code == 200
