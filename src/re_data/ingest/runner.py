from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from re_data.config import Settings
from re_data.ingest.csv_transactions import (
    file_content_hash,
    ingest_csv_file,
    merge_accumulator,
)
from re_data.ingest.index import load_residential_sale_index
from re_data.models.domain import (
    BenchmarkKey,
    DatasetSnapshot,
    DataState,
    DuplicateHashGroup,
    FileIngestReport,
    FileStatus,
    IndexKey,
    IndexSnapshot,
    SkipReasons,
    TotalsSummary,
)

log = logging.getLogger(__name__)


def _file_status(acc_rows_read: int, acc_rows_accepted: int, skip: SkipReasons) -> FileStatus:
    if acc_rows_accepted == 0:
        return "failed"
    if acc_rows_read > 0 and (skip.unparseable / acc_rows_read) > 0.5:
        return "failed"
    if skip.unparseable > 0:
        return "partial"
    return "loaded"


def _compute_dataset_version(path_hashes: list[tuple[str, str | None]]) -> str:
    lines = [f"{path}\n{content_hash or 'MISSING'}\n" for path, content_hash in path_hashes]
    lines.sort()
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _compute_state(
    files: list[FileIngestReport],
    *,
    index_configured: bool,
    accepted_rows: int,
) -> DataState:
    if accepted_rows == 0:
        return "degraded"

    for f in files:
        if f.schema == "residential_sale_index":
            if index_configured and f.status in ("missing", "failed"):
                return "degraded"
            continue
        if f.status in ("missing", "failed"):
            return "degraded"

    if index_configured:
        index_file = next((f for f in files if f.schema == "residential_sale_index"), None)
        if index_file is None or index_file.status not in ("loaded", "partial"):
            return "degraded"

    return "complete"


def run_ingest(settings: Settings) -> DatasetSnapshot:
    grouped: dict[BenchmarkKey, list[Decimal]] = {}
    last_dates: dict[BenchmarkKey, str] = {}
    files: list[FileIngestReport] = []
    path_hashes: list[tuple[str, str | None]] = []

    hash_to_first_path: dict[str, str] = {}
    hash_to_paths: dict[str, list[str]] = defaultdict(list)

    for path in settings.transaction_paths():
        path_str = str(path)
        if not path.exists():
            files.append(
                FileIngestReport(
                    path=path_str,
                    name=path.name,
                    status="missing",
                    schema=None,
                    content_hash=None,
                    size_bytes=None,
                    rows_read=0,
                    rows_accepted=0,
                    rows_skipped=0,
                    skip_reasons=SkipReasons(),
                    duplicate_content_hash_of=None,
                )
            )
            path_hashes.append((path_str, None))
            continue

        try:
            content_hash, size_bytes = file_content_hash(path)
        except OSError:
            files.append(
                FileIngestReport(
                    path=path_str,
                    name=path.name,
                    status="failed",
                    schema=None,
                    content_hash=None,
                    size_bytes=None,
                    rows_read=0,
                    rows_accepted=0,
                    rows_skipped=0,
                    skip_reasons=SkipReasons(),
                    duplicate_content_hash_of=None,
                )
            )
            path_hashes.append((path_str, None))
            continue

        hash_to_paths[content_hash].append(path_str)
        duplicate_of: str | None = None
        if content_hash in hash_to_first_path:
            duplicate_of = hash_to_first_path[content_hash]
        else:
            hash_to_first_path[content_hash] = path_str

        path_hashes.append((path_str, content_hash))

        if duplicate_of is not None:
            files.append(
                FileIngestReport(
                    path=path_str,
                    name=path.name,
                    status="loaded",
                    schema=None,
                    content_hash=content_hash,
                    size_bytes=size_bytes,
                    rows_read=0,
                    rows_accepted=0,
                    rows_skipped=0,
                    skip_reasons=SkipReasons(),
                    duplicate_content_hash_of=duplicate_of,
                )
            )
            continue

        try:
            acc = ingest_csv_file(path, settings)
        except Exception:
            log.warning("CSV ingest failed for %s", path_str, exc_info=True)
            files.append(
                FileIngestReport(
                    path=path_str,
                    name=path.name,
                    status="failed",
                    schema=None,
                    content_hash=content_hash,
                    size_bytes=size_bytes,
                    rows_read=0,
                    rows_accepted=0,
                    rows_skipped=0,
                    skip_reasons=SkipReasons(),
                    duplicate_content_hash_of=None,
                )
            )
            continue

        merge_accumulator(grouped, last_dates, acc)
        status = _file_status(acc.rows_read, acc.rows_accepted, acc.skip_reasons)
        files.append(
            FileIngestReport(
                path=path_str,
                name=path.name,
                status=status,
                schema=acc.detected_schema,
                content_hash=content_hash,
                size_bytes=size_bytes,
                rows_read=acc.rows_read,
                rows_accepted=acc.rows_accepted,
                rows_skipped=acc.rows_skipped,
                skip_reasons=acc.skip_reasons,
                duplicate_content_hash_of=None,
            )
        )

    index_path = settings.index_path()
    index_configured = index_path is not None
    index_data: dict[IndexKey, IndexSnapshot] = {}
    if index_path is not None:
        path_str = str(index_path)
        if not index_path.exists():
            files.append(
                FileIngestReport(
                    path=path_str,
                    name=index_path.name,
                    status="missing",
                    schema=None,
                    content_hash=None,
                    size_bytes=None,
                    rows_read=0,
                    rows_accepted=0,
                    rows_skipped=0,
                    skip_reasons=SkipReasons(),
                    duplicate_content_hash_of=None,
                )
            )
            path_hashes.append((path_str, None))
        else:
            try:
                content_hash, size_bytes = file_content_hash(index_path)
                path_hashes.append((path_str, content_hash))
                hash_to_paths[content_hash].append(path_str)
                idx_result = load_residential_sale_index(index_path)
                index_data = idx_result.index
                index_status: FileStatus = "loaded"
                if idx_result.rows_accepted == 0:
                    index_status = "failed"
                elif idx_result.skip_reasons.unparseable > 0:
                    index_status = "partial"
                files.append(
                    FileIngestReport(
                        path=path_str,
                        name=index_path.name,
                        status=index_status,
                        schema="residential_sale_index",
                        content_hash=content_hash,
                        size_bytes=size_bytes,
                        rows_read=idx_result.rows_read,
                        rows_accepted=idx_result.rows_accepted,
                        rows_skipped=idx_result.skip_reasons.rows_skipped,
                        skip_reasons=idx_result.skip_reasons,
                        duplicate_content_hash_of=None,
                    )
                )
            except Exception:
                log.warning("Index CSV ingest failed for %s", path_str, exc_info=True)
                files.append(
                    FileIngestReport(
                        path=path_str,
                        name=index_path.name,
                        status="failed",
                        schema="residential_sale_index",
                        content_hash=None,
                        size_bytes=None,
                        rows_read=0,
                        rows_accepted=0,
                        rows_skipped=0,
                        skip_reasons=SkipReasons(),
                        duplicate_content_hash_of=None,
                    )
                )
                path_hashes.append((path_str, None))

    accepted_rows = sum(len(vals) for vals in grouped.values())
    latest_date: str | None = None
    if last_dates:
        latest_date = max(last_dates.values())

    duplicate_groups = tuple(
        DuplicateHashGroup(content_hash=h, paths=tuple(paths))
        for h, paths in hash_to_paths.items()
        if len(paths) > 1
    )

    immutable_tx = {k: tuple(v) for k, v in grouped.items()}
    version = _compute_dataset_version(path_hashes)
    state = _compute_state(files, index_configured=index_configured, accepted_rows=accepted_rows)

    return DatasetSnapshot(
        version=version,
        ingested_at=datetime.now(UTC),
        state=state,
        files=tuple(files),
        transactions=immutable_tx,
        last_dates=dict(last_dates),
        index=index_data,
        totals=TotalsSummary(
            accepted_transaction_rows=accepted_rows,
            index_loaded=bool(index_data),
            index_snapshot_count=len(index_data),
            latest_transaction_date=latest_date,
        ),
        duplicate_content_hashes=duplicate_groups,
    )
