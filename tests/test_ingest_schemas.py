from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from re_data.config import SQM_TO_SQFT
from re_data.ingest.csv_transactions import file_content_hash
from re_data.ingest.runner import run_ingest
from tests.conftest import make_settings, write_dld_csv, write_index_csv, write_recent_csv


def test_schema_detection_and_sale_acceptance(tmp_path):
    write_dld_csv(
        tmp_path / "Transactions.csv",
        ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"],
    )
    write_recent_csv(
        tmp_path / "transactions-2026-02-23.csv",
        ["Sell,1500000,80,Marina,apartment,1\n"],
    )
    settings = make_settings(
        tmp_path,
        benchmarks_paths=f"{tmp_path / 'transactions-2026-02-23.csv'};{tmp_path / 'Transactions.csv'}",
        index_file="",
    )
    snap = run_ingest(settings)
    schemas = {f.name: f.schema for f in snap.files if f.schema != "residential_sale_index"}
    assert schemas["Transactions.csv"] == "dld_transactions"
    assert schemas["transactions-2026-02-23.csv"] == "recent_transactions"
    assert snap.totals.accepted_transaction_rows == 2


def test_mortgage_gift_excluded_sale_included(tmp_path):
    write_dld_csv(
        tmp_path / "Transactions.csv",
        [
            "1,1000000,100,Area,Mortgage Bldg,flat,1,Mortgages,Mortgage Registration,2026-01-01\n",
            "2,1000000,100,Area,Gift Bldg,flat,1,Gifts,Gift,2026-01-01\n",
            "3,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n",
        ],
    )
    settings = make_settings(tmp_path, benchmarks_paths=str(tmp_path / "Transactions.csv"), index_file="")
    snap = run_ingest(settings)
    f = next(x for x in snap.files if x.name == "Transactions.csv")
    assert f.rows_accepted == 1
    assert f.skip_reasons.filtered_procedure == 2


def test_sqm_conversion_default(tmp_path):
    write_dld_csv(
        tmp_path / "Transactions.csv",
        ["1,1076391,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"],
    )
    settings = make_settings(
        tmp_path,
        benchmarks_paths=str(tmp_path / "Transactions.csv"),
        index_file="",
        dld_area_unit="sqm",
    )
    snap = run_ingest(settings)
    key = ("dubai", "dubai marina", "tower", "flat", 2)
    ppsf = snap.transactions[key][0]
    expected = Decimal("1076391") / (Decimal("100") * SQM_TO_SQFT)
    assert abs(ppsf - expected) < Decimal("0.01")
    assert abs(ppsf - Decimal("1000")) < Decimal("1")


def test_sqft_no_conversion(tmp_path):
    write_dld_csv(
        tmp_path / "Transactions.csv",
        ["1,1000000,1000,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"],
    )
    settings = make_settings(
        tmp_path,
        benchmarks_paths=str(tmp_path / "Transactions.csv"),
        index_file="",
        dld_area_unit="sqft",
    )
    snap = run_ingest(settings)
    key = ("dubai", "dubai marina", "tower", "flat", 2)
    assert snap.transactions[key][0] == Decimal("1000")


def test_ppsf_bounds(tmp_path):
    rows = [
        "1,50000,1000,Area A,B,flat,1,Sales,Sale,2026-01-01\n",
        "2,500000,1000,Area B,B,flat,1,Sales,Sale,2026-01-01\n",
        "3,50000000,1000,Area C,B,flat,1,Sales,Sale,2026-01-01\n",
    ]
    write_dld_csv(tmp_path / "Transactions.csv", rows)
    settings = make_settings(tmp_path, benchmarks_paths=str(tmp_path / "Transactions.csv"), index_file="")
    snap = run_ingest(settings)
    f = next(x for x in snap.files if x.name == "Transactions.csv")
    assert f.rows_accepted == 1
    assert f.skip_reasons.out_of_bounds_ppsf == 2


def test_index_latest_per_segment_horizon(tmp_path):
    write_index_csv(
        tmp_path / "index.csv",
        [
            "2026-01-01,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1\n",
            "2026-02-01,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2\n",
        ],
    )
    settings = make_settings(tmp_path, benchmarks_paths="", index_file="index.csv")
    snap = run_ingest(settings)
    assert snap.totals.index_snapshot_count == 9
    assert all(s.date == "2026-02-01" for s in snap.index.values())


def test_env_path_parsing_quotes_and_empty_segments(tmp_path):
    p1 = tmp_path / "a.csv"
    p2 = tmp_path / "b.csv"
    write_dld_csv(p1, ["1,2000000,100,Area,B,flat,1,Sales,Sale,2026-01-01\n"])
    write_dld_csv(p2, ["2,2000000,100,Area,B,flat,1,Sales,Sale,2026-01-01\n"])
    raw = f'"{p1}" ; ;{p2}'
    settings = make_settings(tmp_path, benchmarks_paths=raw, index_file="")
    assert len(settings.transaction_paths()) == 2
    snap = run_ingest(settings)
    assert snap.totals.accepted_transaction_rows == 2


def test_defaults_ppsf_and_unit():
    settings = make_settings(Path("/nonexistent"), benchmarks_paths="", index_file="")
    assert settings.ppsf_min == Decimal("100")
    assert settings.ppsf_max == Decimal("20000")
    assert settings.dld_area_unit == "sqm"


def test_binary_garbage_file_failed(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\x00\x01\x02\xff\xfe")
    settings = make_settings(tmp_path, benchmarks_paths=str(bad), index_file="")
    snap = run_ingest(settings)
    f = next(x for x in snap.files if x.name == "bad.csv")
    assert f.status == "failed"
    assert snap.state == "degraded"


def test_partial_unparseable_rows(tmp_path):
    rows = ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"] * 5
    rows += [
        "2,,100,Area,B,flat,1,Sales,Sale,2026-01-01\n",
        "3,2000000,,Area,B,flat,1,Sales,Sale,2026-01-01\n",
    ]
    write_dld_csv(tmp_path / "Transactions.csv", rows)
    settings = make_settings(tmp_path, benchmarks_paths=str(tmp_path / "Transactions.csv"), index_file="")
    snap = run_ingest(settings)
    f = next(x for x in snap.files if x.name == "Transactions.csv")
    assert f.status == "partial"
    assert f.rows_accepted == 5
    assert f.skip_reasons.unparseable == 2


def test_over_fifty_percent_unparseable_failed(tmp_path):
    rows = ["1,2000000,100,Area,B,flat,1,Sales,Sale,2026-01-01\n"]
    rows += ["2,,100,Area,B,flat,1,Sales,Sale,2026-01-01\n"] * 3
    write_dld_csv(tmp_path / "Transactions.csv", rows)
    settings = make_settings(tmp_path, benchmarks_paths=str(tmp_path / "Transactions.csv"), index_file="")
    snap = run_ingest(settings)
    f = next(x for x in snap.files if x.name == "Transactions.csv")
    assert f.status == "failed"
    assert snap.state == "degraded"


# ---------------------------------------------------------------------------
# REL-01 regression: file_content_hash must use streaming (chunked) reads
# ---------------------------------------------------------------------------


def test_file_content_hash_matches_full_content_sha256(tmp_path):
    """REL-01: streaming hash must equal hashlib.sha256(full_bytes).hexdigest()."""
    content = b"header,col\nrow1,val1\nrow2,val2\n" * 500
    p = tmp_path / "sample.csv"
    p.write_bytes(content)

    expected_digest = hashlib.sha256(content).hexdigest()
    expected_size = len(content)

    actual_digest, actual_size = file_content_hash(p)

    assert actual_digest == expected_digest
    assert actual_size == expected_size


def test_file_content_hash_size_matches_file_stat(tmp_path):
    """REL-01: reported size_bytes must equal the file's on-disk size."""
    content = b"x" * 4096 * 3
    p = tmp_path / "large.csv"
    p.write_bytes(content)

    _, size = file_content_hash(p)

    assert size == p.stat().st_size


# ---------------------------------------------------------------------------
# REL-02 regression: ingest exceptions must be logged (not swallowed silently)
# ---------------------------------------------------------------------------


def test_ingest_csv_exception_is_logged(tmp_path, caplog):
    """REL-02: when ingest_csv_file raises, runner must log a WARNING with exc_info."""
    csv_path = tmp_path / "bad.csv"
    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"])
    settings = make_settings(tmp_path, benchmarks_paths=str(csv_path), index_file="")

    with patch("re_data.ingest.runner.ingest_csv_file", side_effect=RuntimeError("simulated parse crash")):
        with caplog.at_level(logging.WARNING, logger="re_data.ingest.runner"):
            snap = run_ingest(settings)

    assert any("bad.csv" in r.message for r in caplog.records)
    assert snap.files[0].status == "failed"


def test_index_csv_exception_is_logged(tmp_path, caplog):
    """REL-02: when index load raises, runner must log a WARNING with exc_info."""
    csv_path = tmp_path / "Transactions.csv"
    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"])
    index_path = tmp_path / "index.csv"
    index_path.write_text("bad content\n", encoding="utf-8")
    settings = make_settings(tmp_path, benchmarks_paths=str(csv_path), index_file="index.csv")

    with patch("re_data.ingest.runner.load_residential_sale_index", side_effect=RuntimeError("simulated index crash")):
        with caplog.at_level(logging.WARNING, logger="re_data.ingest.runner"):
            snap = run_ingest(settings)

    assert any("index.csv" in r.message for r in caplog.records)
    index_file = next(f for f in snap.files if f.name == "index.csv")
    assert index_file.status == "failed"
