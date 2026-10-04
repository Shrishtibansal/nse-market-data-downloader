"""Turns a raw JSON payload into a flat list of dict rows."""
from __future__ import annotations

import logging
from typing import Any

from .exceptions import InvalidResponseError

log = logging.getLogger(__name__)


def _walk(payload: Any, path: tuple[str, ...]) -> Any:
    cur = payload
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return None
    return cur


def _largest_record_list(payload: Any) -> list[dict] | None:
    """Fallback: find the biggest list-of-dicts anywhere in the JSON."""
    best: list[dict] | None = None
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            if node and all(isinstance(i, dict) for i in node):
                if best is None or len(node) > len(best):
                    best = node
        elif isinstance(node, dict):
            stack.extend(node.values())
    return best


def flatten(record: dict, parent: str = "", sep: str = "_") -> dict:
    """{'meta': {'a': 1}} -> {'meta_a': 1}  (CSV needs flat columns)."""
    flat: dict = {}
    for key, value in record.items():
        name = f"{parent}{sep}{key}" if parent else str(key)
        if isinstance(value, dict):
            flat.update(flatten(value, name, sep))
        elif isinstance(value, list):
            flat[name] = ";".join(map(str, value))
        else:
            flat[name] = value
    return flat


def extract_records(payload: Any, data_path: tuple[str, ...], dataset_key: str = "") -> list[dict]:
    if not isinstance(payload, (dict, list)):
        raise InvalidResponseError(f"expected JSON object/array, got {type(payload).__name__}")

    found = _walk(payload, data_path) if data_path else payload
    if not isinstance(found, list):
        log.warning("[%s] data_path %s not found; falling back to auto-detect. "
                    "NSE may have changed its response format.", dataset_key, list(data_path))
        found = _largest_record_list(payload)
        if found is None:
            raise InvalidResponseError(
                f"no list of records found (top-level keys: {list(payload)[:10] if isinstance(payload, dict) else 'array'})")

    bad = [r for r in found if not isinstance(r, dict)]
    if bad:
        raise InvalidResponseError(f"{len(bad)} record(s) are not JSON objects")
    return [flatten(r) for r in found]
