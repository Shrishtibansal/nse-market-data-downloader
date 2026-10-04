"""Writes CSVs. Layout:  <output_dir>/<dataset>/<dataset>_<YYYY-MM-DD>.csv

Same dataset + same day  ->  same path, so re-running never creates a second file.
Writes are atomic (temp file + os.replace) so a crash can't leave a half CSV.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .exceptions import StorageError

log = logging.getLogger(__name__)


@dataclass
class SaveResult:
    path: Path
    status: str   # created | updated | unchanged


class CsvStorage:
    def __init__(self, base_dir: Path | str) -> None:
        self.base_dir = Path(base_dir)

    def path_for(self, dataset_key: str, day: date) -> Path:
        return self.base_dir / dataset_key / f"{dataset_key}_{day.isoformat()}.csv"

    @staticmethod
    def _render(rows: list[dict], columns: list[str]) -> bytes:
        buf = io.StringIO(newline="")
        writer = csv.DictWriter(buf, fieldnames=columns, restval="", extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    def save(self, dataset_key: str, rows: list[dict], columns: list[str], day: date) -> SaveResult:
        target = self.path_for(dataset_key, day)
        content = self._render(rows, columns)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            existed = target.exists()
            if existed and target.read_bytes() == content:
                return SaveResult(target, "unchanged")
            fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".tmp_", suffix=".csv")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(content)
                os.replace(tmp_name, target)
            except BaseException:
                Path(tmp_name).unlink(missing_ok=True)
                raise
        except OSError as exc:
            raise StorageError(f"could not write {target}: {exc}") from exc
        return SaveResult(target, "updated" if existed else "created")
