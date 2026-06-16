from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from dubai_re_calc.benchmarks import _ingest_csv

from re_data.ingest.runner import run_ingest
from tests.conftest import make_settings, write_dld_csv, write_recent_csv


def _core_ingest(paths: list[Path]) -> tuple[dict, dict]:
    grouped: dict = {}
    last_dates: dict = {}
    for p in paths:
        if p.exists():
            _ingest_csv(p, grouped, last_dates)
    return grouped, last_dates


def test_parity_with_benchmarks_py(tmp_path, monkeypatch):
    write_dld_csv(
        tmp_path / "Transactions.csv",
        [
            "1,2000000,100,Dubai Marina,Tower A,flat,2,Sales,Sale,2026-01-15\n",
            "2,1000000,100,Area,Mortgage Bldg,flat,1,Mortgages,Mortgage,2026-01-01\n",
        ],
    )
    write_recent_csv(
        tmp_path / "transactions-2026-02-23.csv",
        ["Sell,1500000,80,JVC,apartment,1\n"],
    )
    paths = [tmp_path / "transactions-2026-02-23.csv", tmp_path / "Transactions.csv"]
    monkeypatch.setenv("DLD_AREA_UNIT", "sqm")
    monkeypatch.setenv("PPSF_MIN", "100")
    monkeypatch.setenv("PPSF_MAX", "20000")

    core_grouped, _ = _core_ingest(paths)

    settings = make_settings(
        tmp_path,
        benchmarks_paths=f"{paths[0]};{paths[1]}",
        index_file="",
    )
    snap = run_ingest(settings)

    for key, core_vals in core_grouped.items():
        assert key in snap.transactions
        data_vals = list(snap.transactions[key])
        assert len(data_vals) == len(core_vals)
        for a, b in zip(sorted(data_vals), sorted(core_vals), strict=True):
            assert abs(a - b) < Decimal("0.0001")

    for key in snap.transactions:
        assert key in core_grouped
