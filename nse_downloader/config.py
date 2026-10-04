"""Loads config/datasets.yaml into typed, immutable objects."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigError

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "datasets.yaml"


@dataclass(frozen=True)
class NetworkConfig:
    timeout_seconds: float = 15.0
    max_retries: int = 3
    initial_backoff_seconds: float = 1.5
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 20.0
    user_agent: str = "Mozilla/5.0"


@dataclass(frozen=True)
class RequestSpec:
    endpoint: str
    params: dict[str, Any] = field(default_factory=dict)
    tag: str | None = None


@dataclass(frozen=True)
class DatasetConfig:
    key: str
    name: str
    page_url: str
    requests: tuple[RequestSpec, ...]
    data_path: tuple[str, ...]
    required_columns: tuple[str, ...]
    dedupe_keys: tuple[str, ...]
    tag_column: str | None = None


@dataclass(frozen=True)
class AppConfig:
    base_url: str
    network: NetworkConfig
    datasets: dict[str, DatasetConfig]
    output_dir: Path
    timezone: str


def _require(mapping: dict, key: str, where: str) -> Any:
    if key not in mapping:
        raise ConfigError(f"Missing '{key}' in {where}")
    return mapping[key]


def _parse_dataset(key: str, raw: dict) -> DatasetConfig:
    where = f"dataset '{key}'"
    reqs = _require(raw, "requests", where)
    if not reqs:
        raise ConfigError(f"{where} needs at least one request")
    specs = tuple(
        RequestSpec(
            endpoint=_require(r, "endpoint", where),
            params=dict(r.get("params") or {}),
            tag=r.get("tag"),
        )
        for r in reqs
    )
    return DatasetConfig(
        key=key,
        name=_require(raw, "name", where),
        page_url=raw.get("page_url", ""),
        requests=specs,
        data_path=tuple(raw.get("data_path") or ()),
        required_columns=tuple(raw.get("required_columns") or ()),
        dedupe_keys=tuple(raw.get("dedupe_keys") or ()),
        tag_column=raw.get("tag_column"),
    )


def load_config(path: Path | str | None = None, output_dir: Path | str | None = None) -> AppConfig:
    """Precedence for output dir: CLI arg > NSE_OUTPUT_DIR env var > yaml > ./data"""
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Config file is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("Config root must be a mapping")

    datasets_raw = _require(raw, "datasets", "config root")
    datasets = {k: _parse_dataset(k, v) for k, v in datasets_raw.items()}
    out = output_dir or os.environ.get("NSE_OUTPUT_DIR") or raw.get("output_dir") or "data"

    return AppConfig(
        base_url=_require(raw, "base_url", "config root").rstrip("/"),
        network=NetworkConfig(**(raw.get("network") or {})),
        datasets=datasets,
        output_dir=Path(out),
        timezone=raw.get("timezone", "Asia/Kolkata"),
    )
