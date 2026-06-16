from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from re_data.ingest.runner import run_ingest
from re_data.store.dataset_store import DatasetStore, ReloadInProgressError, ReloadTimeoutError
from tests.conftest import make_settings, write_dld_csv


def test_missing_file_starts_degraded_other_files_load(tmp_path):
    write_dld_csv(
        tmp_path / "Transactions.csv",
        ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"],
    )
    paths = f"{tmp_path / 'missing.csv'};{tmp_path / 'Transactions.csv'}"
    settings = make_settings(tmp_path, benchmarks_paths=paths, index_file="")
    store = DatasetStore(settings)
    store.initial_load()
    snap = store.get_active()
    assert snap is not None
    assert snap.state == "degraded"
    assert snap.totals.accepted_transaction_rows == 1


def test_zero_valid_rows_degraded(tmp_path):
    write_dld_csv(
        tmp_path / "Transactions.csv",
        ["1,1000000,100,Area,B,flat,1,Mortgages,Mortgage,2026-01-01\n"],
    )
    settings = make_settings(tmp_path, benchmarks_paths=str(tmp_path / "Transactions.csv"), index_file="")
    store = DatasetStore(settings)
    store.initial_load()
    snap = store.get_active()
    assert snap is not None
    assert snap.state == "degraded"
    assert snap.totals.accepted_transaction_rows == 0


def test_content_change_new_version_same_bytes_same_version(tmp_path):
    csv_path = tmp_path / "Transactions.csv"
    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"])
    settings = make_settings(tmp_path, benchmarks_paths=str(csv_path), index_file="")
    v1 = run_ingest(settings).version
    time.sleep(0.01)
    v2 = run_ingest(settings).version
    assert v1 == v2

    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n", "2,3000000,100,JVC,T,flat,1,Sales,Sale,2026-01-02\n"])
    v3 = run_ingest(settings).version
    assert v3 != v1


@pytest.mark.asyncio
async def test_reload_serves_old_snapshot_during_ingest(tmp_path):
    csv_path = tmp_path / "Transactions.csv"
    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"])
    settings = make_settings(tmp_path, benchmarks_paths=str(csv_path), index_file="")
    store = DatasetStore(settings)
    store.initial_load()
    old_version = store.get_active().version

    original_to_thread = asyncio.to_thread

    async def slow_to_thread(func, *args, **kwargs):
        await asyncio.sleep(0.05)
        return await original_to_thread(func, *args, **kwargs)

    with patch("re_data.store.dataset_store.asyncio.to_thread", new=slow_to_thread):
        task = asyncio.create_task(store.reload())
        await asyncio.sleep(0.01)
        assert store.get_active().version == old_version
        await task


@pytest.mark.asyncio
async def test_reload_after_delete_degraded(tmp_path):
    csv_path = tmp_path / "Transactions.csv"
    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"])
    settings = make_settings(tmp_path, benchmarks_paths=str(csv_path), index_file="")
    store = DatasetStore(settings)
    store.initial_load()
    csv_path.unlink()
    snap = await store.reload()
    assert snap.state == "degraded"


@pytest.mark.asyncio
async def test_reload_unchanged_content_same_version_new_ingested_at(tmp_path):
    csv_path = tmp_path / "Transactions.csv"
    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"])
    settings = make_settings(tmp_path, benchmarks_paths=str(csv_path), index_file="")
    store = DatasetStore(settings)
    store.initial_load()
    v1 = store.get_active().version
    t1 = store.get_active().ingested_at
    await asyncio.sleep(0.02)
    snap = await store.reload()
    assert snap.version == v1
    assert snap.ingested_at > t1


@pytest.mark.asyncio
async def test_concurrent_reload_409(tmp_path):
    csv_path = tmp_path / "Transactions.csv"
    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"])
    settings = make_settings(tmp_path, benchmarks_paths=str(csv_path), index_file="")
    store = DatasetStore(settings)
    store.initial_load()

    await store._reload_lock.acquire()
    try:
        with pytest.raises(ReloadInProgressError):
            await store.reload()
    finally:
        store._reload_lock.release()


# ---------------------------------------------------------------------------
# REL-03 regression: reload timeout must release lock and raise ReloadTimeoutError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reload_timeout_raises_and_releases_lock(tmp_path):
    """REL-03: asyncio.wait_for timeout must raise ReloadTimeoutError and release the lock."""
    csv_path = tmp_path / "Transactions.csv"
    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"])
    settings = make_settings(tmp_path, benchmarks_paths=str(csv_path), index_file="")
    store = DatasetStore(settings, max_reload_s=0.05)
    store.initial_load()

    async def _hanging_ingest(*_args, **_kwargs) -> None:
        await asyncio.sleep(60)

    with patch("re_data.store.dataset_store.asyncio.to_thread", new=_hanging_ingest):
        with pytest.raises(ReloadTimeoutError):
            await store.reload()

    assert not store.reload_in_progress


@pytest.mark.asyncio
async def test_reload_succeeds_after_previous_timeout(tmp_path):
    """REL-03: after a timeout the lock is released and a subsequent reload completes normally."""
    csv_path = tmp_path / "Transactions.csv"
    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"])
    settings = make_settings(tmp_path, benchmarks_paths=str(csv_path), index_file="")
    store = DatasetStore(settings, max_reload_s=0.05)
    store.initial_load()
    old_version = store.get_active().version  # type: ignore[union-attr]

    async def _hanging_ingest(*_args, **_kwargs) -> None:
        await asyncio.sleep(60)

    with patch("re_data.store.dataset_store.asyncio.to_thread", new=_hanging_ingest):
        with pytest.raises(ReloadTimeoutError):
            await store.reload()

    snap = await store.reload()
    assert snap.version == old_version


def test_no_writes_to_data_dir(tmp_path):
    csv_path = tmp_path / "Transactions.csv"
    write_dld_csv(csv_path, ["1,2000000,100,Dubai Marina,Tower,flat,2,Sales,Sale,2026-01-01\n"])
    before = {p: (p.stat().st_mtime, p.read_bytes()) for p in tmp_path.iterdir() if p.is_file()}
    settings = make_settings(tmp_path, benchmarks_paths=str(csv_path), index_file="")
    store = DatasetStore(settings)
    store.initial_load()
    asyncio.run(store.reload())
    after = {p: (p.stat().st_mtime, p.read_bytes()) for p in tmp_path.iterdir() if p.is_file()}
    assert before == after
