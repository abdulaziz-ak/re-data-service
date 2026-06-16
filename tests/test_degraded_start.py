from __future__ import annotations

from re_data.ingest.runner import run_ingest
from tests.conftest import make_settings, write_dld_csv


def test_missing_transaction_file_degraded(tmp_path):
    write_dld_csv(
        tmp_path / "Transactions.csv",
        ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"],
    )
    paths = f"{tmp_path / 'missing.csv'};{tmp_path / 'Transactions.csv'}"
    settings = make_settings(tmp_path, benchmarks_paths=paths, index_file="")
    snap = run_ingest(settings)
    missing = next(f for f in snap.files if f.status == "missing")
    assert missing.name == "missing.csv"
    assert snap.state == "degraded"


def test_all_missing_zero_rows_degraded(tmp_path):
    settings = make_settings(
        tmp_path,
        benchmarks_paths=f"{tmp_path / 'a.csv'};{tmp_path / 'b.csv'}",
        index_file="",
    )
    snap = run_ingest(settings)
    assert snap.totals.accepted_transaction_rows == 0
    assert snap.state == "degraded"


def test_dataset_degraded_still_200(client_factory, tmp_path):
    settings = make_settings(
        tmp_path,
        benchmarks_paths=str(tmp_path / "missing.csv"),
        index_file="",
    )
    client = client_factory(settings)
    resp = client.get("/v1/dataset")
    assert resp.status_code == 200
    assert resp.json()["state"] == "degraded"
