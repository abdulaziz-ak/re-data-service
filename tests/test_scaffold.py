from __future__ import annotations


def test_app_imports_and_docs(sample_complete_dataset, client_factory):
    client = client_factory(sample_complete_dataset)
    assert client.get("/docs").status_code == 200


def test_root_lists_health(client_factory, sample_complete_dataset):
    client = client_factory(sample_complete_dataset)
    body = client.get("/").json()
    assert body["health"] == "/health"


def test_not_found_error_shape(client_factory, sample_complete_dataset):
    client = client_factory(sample_complete_dataset)
    resp = client.get("/v1/does-not-exist")
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert isinstance(data["details"], list)
