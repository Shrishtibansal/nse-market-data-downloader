"""Quality gate. Nothing reaches disk unless it passes through here."""
from __future__ import annotations

from dataclasses import dataclass

from .config import DatasetConfig
from .exceptions import EmptyDataError, ValidationError


@dataclass
class ValidationResult:
    rows: list[dict]
    columns: list[str]
    duplicates_removed: int
    dropped_invalid: int


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate(rows: list[dict], ds: DatasetConfig) -> ValidationResult:
    if not rows:
        raise EmptyDataError("response contained zero records")

    columns: list[str] = []
    seen_cols: set[str] = set()
    for row in rows:
        for col in row:
            if col not in seen_cols:
                seen_cols.add(col)
                columns.append(col)

    missing = [c for c in ds.required_columns if c not in seen_cols]
    if missing:
        raise ValidationError(f"missing required column(s) {missing}; got {columns[:15]}")

    valid = [r for r in rows if all(not _blank(r.get(c)) for c in ds.required_columns)]
    dropped = len(rows) - len(valid)
    if not valid:
        raise EmptyDataError("every record had blank required fields")

    unique: list[dict] = []
    seen_keys: set[tuple] = set()
    for row in valid:
        key = tuple(str(row.get(k, "")).strip().upper() for k in ds.dedupe_keys) if ds.dedupe_keys else None
        if key is not None:
            if key in seen_keys:
                continue
            seen_keys.add(key)
        unique.append(row)

    return ValidationResult(unique, columns, len(valid) - len(unique), dropped)
