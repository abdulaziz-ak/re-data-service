from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from re_data.config import Settings, get_settings
from re_data.main import create_app
from re_data.store.dataset_store import DatasetStore

CORE_SRC = Path(__file__).resolve().parents[2] / "realestate-core-service" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))


DLD_HEADER = (
    "transaction_id,actual_worth,procedure_area,area_name_en,building_name_en,"
    "property_sub_type_en,rooms_en,trans_group_en,procedure_name_en,instance_date\n"
)

RECENT_HEADER = "PROCEDURE_EN,TRANS_VALUE,PROCEDURE_AREA,AREA_EN,PROP_SB_TYPE_EN,ROOMS_EN\n"

INDEX_HEADER = (
    "first_date_of_month,"
    "all_monthly_index,all_monthly_price_index,"
    "all_quarterly_index,all_quarterly_price_index,"
    "all_yearly_index,all_yearly_price_index,"
    "flat_monthly_index,flat_monthly_price_index,"
    "flat_quarterly_index,flat_quarterly_price_index,"
    "flat_yearly_index,flat_yearly_price_index,"
    "villa_monthly_index,villa_monthly_price_index,"
    "villa_quarterly_index,villa_quarterly_price_index,"
    "villa_yearly_index,villa_yearly_price_index\n"
)


def write_dld_csv(path: Path, rows: list[str]) -> None:
    path.write_text(DLD_HEADER + "".join(rows), encoding="utf-8")


def write_recent_csv(path: Path, rows: list[str]) -> None:
    path.write_text(RECENT_HEADER + "".join(rows), encoding="utf-8")


def write_index_csv(path: Path, rows: list[str]) -> None:
    path.write_text(INDEX_HEADER + "".join(rows), encoding="utf-8")


def make_settings(
    tmp_path: Path,
    *,
    transaction_files: list[str] | None = None,
    index_file: str | None = "index.csv",
    dld_area_unit: str = "sqm",
    ppsf_min: str = "100",
    ppsf_max: str = "20000",
    benchmarks_paths: str | None = None,
) -> Settings:
    if benchmarks_paths is None:
        paths: list[str] = []
        if transaction_files:
            for name in transaction_files:
                p = tmp_path / name
                if not p.exists():
                    p.write_text("placeholder\n")
                paths.append(str(p))
        benchmarks_paths = ";".join(paths)

    index_path = ""
    if index_file:
        index_path = str(tmp_path / index_file)

    return Settings(
        benchmarks_csv_paths=benchmarks_paths,
        index_csv_path=index_path,
        dld_area_unit=dld_area_unit,
        ppsf_min=Decimal(ppsf_min),
        ppsf_max=Decimal(ppsf_max),
        app_env="test",
    )


@pytest.fixture
def sample_dld_sale_row() -> str:
    return (
        "1,2000000,100,Dubai Marina,Tower A,flat,2,Sales,Sale,2026-01-15\n"
    )


@pytest.fixture
def sample_complete_dataset(tmp_path: Path, sample_dld_sale_row: str) -> Settings:
    write_dld_csv(tmp_path / "Transactions.csv", [sample_dld_sale_row])
    write_recent_csv(
        tmp_path / "transactions-2026-02-23.csv",
        ["Sell,1500000,80,Marina,apartment,1\n"],
    )
    write_index_csv(
        tmp_path / "index.csv",
        [
            "2026-01-01,1.0,1.0,1.1,1.1,1.2,1.2,0.9,0.9,1.0,1.0,1.1,1.1,0.8,0.8,0.9,0.9,1.0,1.0\n",
            "2026-02-01,1.1,1.1,1.2,1.2,1.3,1.3,1.0,1.0,1.1,1.1,1.2,1.2,0.9,0.9,1.0,1.0,1.1,1.1\n",
        ],
    )
    paths = f"{tmp_path / 'transactions-2026-02-23.csv'};{tmp_path / 'Transactions.csv'}"
    return make_settings(tmp_path, benchmarks_paths=paths, index_file="index.csv")


@pytest.fixture
def client_factory():
    clients: list[TestClient] = []

    def _factory(settings: Settings) -> TestClient:
        get_settings.cache_clear()
        os.environ["BENCHMARKS_CSV_PATHS"] = settings.benchmarks_csv_paths
        os.environ["INDEX_CSV_PATH"] = settings.index_csv_path
        os.environ["DLD_AREA_UNIT"] = settings.dld_area_unit
        os.environ["PPSF_MIN"] = str(settings.ppsf_min)
        os.environ["PPSF_MAX"] = str(settings.ppsf_max)
        os.environ["APP_ENV"] = settings.app_env
        os.environ["REDIS_URL"] = settings.redis_url
        os.environ["MARKET_CACHE_TTL_S"] = str(settings.market_cache_ttl_s)

        client = TestClient(create_app())
        client.__enter__()
        clients.append(client)
        return client

    yield _factory

    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def store_factory():
    def _factory(settings: Settings) -> DatasetStore:
        store = DatasetStore(settings)
        store.initial_load()
        return store

    return _factory


def make_market_snapshot(
    tmp_path: Path,
    *,
    transaction_csv_rows: list[str] | None = None,
    index_csv_rows: list[str] | None = None,
):
    """Helper: build a DatasetSnapshot from minimal CSV fixtures for market tests.

    Returns the snapshot directly (no HTTP layer needed for unit-level market tests).
    """
    from re_data.ingest.runner import run_ingest

    if transaction_csv_rows:
        write_dld_csv(tmp_path / "Transactions.csv", transaction_csv_rows)
        paths = str(tmp_path / "Transactions.csv")
    else:
        paths = ""

    if index_csv_rows:
        write_index_csv(tmp_path / "index.csv", index_csv_rows)
        index_file = "index.csv"
    else:
        index_file = ""

    settings = make_settings(tmp_path, benchmarks_paths=paths, index_file=index_file)
    return run_ingest(settings)
