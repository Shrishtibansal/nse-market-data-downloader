"""Orchestration: fetch -> parse -> validate -> store, one dataset at a time.

Each dataset is wrapped in its own try/except, so one failure never stops the rest.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .config import DatasetConfig
from .exceptions import NSEError
from .parsers import extract_records
from .storage import CsvStorage
from .validation import validate

log = logging.getLogger(__name__)


@dataclass
class DatasetResult:
    key: str
    name: str
    success: bool
    records: int = 0
    duplicates_removed: int = 0
    dropped_invalid: int = 0
    file_status: str | None = None
    path: Path | None = None
    error: str | None = None
    duration_seconds: float = 0.0


def run_dataset(ds: DatasetConfig, client: Any, storage: CsvStorage, day: date) -> DatasetResult:
    start = time.monotonic()
    log.info("[%s] attempting download (%d request(s))", ds.key, len(ds.requests))
    try:
        rows: list[dict] = []
        for spec in ds.requests:
            payload = client.get_json(spec.endpoint, spec.params)
            records = extract_records(payload, ds.data_path, ds.key)
            if ds.tag_column and spec.tag:
                records = [{ds.tag_column: spec.tag, **r} for r in records]
            rows.extend(records)

        checked = validate(rows, ds)
        saved = storage.save(ds.key, checked.rows, checked.columns, day)
    except NSEError as exc:
        elapsed = time.monotonic() - start
        log.error("[%s] FAILED after %.1fs: %s", ds.key, elapsed, exc)
        return DatasetResult(ds.key, ds.name, False, error=str(exc), duration_seconds=elapsed)
    except Exception as exc:  # a genuine bug must not kill the other datasets
        elapsed = time.monotonic() - start
        log.exception("[%s] UNEXPECTED error", ds.key)
        return DatasetResult(ds.key, ds.name, False, error=f"unexpected: {exc!r}", duration_seconds=elapsed)

    elapsed = time.monotonic() - start
    log.info("[%s] SUCCESS records=%d duplicates_removed=%d dropped_invalid=%d file=%s (%s) in %.1fs",
             ds.key, len(checked.rows), checked.duplicates_removed, checked.dropped_invalid,
             saved.path, saved.status, elapsed)
    return DatasetResult(ds.key, ds.name, True, len(checked.rows), checked.duplicates_removed,
                         checked.dropped_invalid, saved.status, saved.path, None, elapsed)


def run_all(datasets: Iterable[DatasetConfig], client: Any, storage: CsvStorage, day: date) -> list[DatasetResult]:
    results = [run_dataset(ds, client, storage, day) for ds in datasets]
    ok = sum(r.success for r in results)
    log.info("RUN SUMMARY: %d/%d datasets succeeded", ok, len(results))
    for r in results:
        log.info("  %-24s %s %s", r.key, "OK  " if r.success else "FAIL",
                 f"{r.records} records -> {r.path}" if r.success else r.error)
    return results
