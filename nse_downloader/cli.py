"""Entry point: argument parsing + wiring. No business logic here."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from .client import NSEClient
from .config import load_config
from .exceptions import ConfigError
from .logging_setup import setup_logging
from .pipeline import run_all
from .storage import CsvStorage

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="main.py", description="Download NSE market-data CSVs.")
    p.add_argument("-d", "--dataset", nargs="+", metavar="KEY",
                   help="dataset key(s) to download (default: all). Use --list to see keys.")
    p.add_argument("--list", action="store_true", help="list available datasets and exit")
    p.add_argument("-o", "--output-dir", help="where to store CSVs (default: ./data)")
    p.add_argument("-c", "--config", help="path to datasets.yaml")
    p.add_argument("--log-dir", default="logs")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_dir, args.log_level)
    try:
        cfg = load_config(args.config, args.output_dir)
    except ConfigError as exc:
        log.error("Configuration error: %s", exc)
        return 2

    if args.list:
        for key, ds in cfg.datasets.items():
            print(f"{key:24s} {ds.name}")
        return 0

    keys = args.dataset or list(cfg.datasets)
    unknown = [k for k in keys if k not in cfg.datasets]
    if unknown:
        log.error("Unknown dataset(s): %s. Available: %s", unknown, list(cfg.datasets))
        return 2

    day = datetime.now(ZoneInfo(cfg.timezone)).date()
    log.info("Starting run for %s | datasets=%s | output=%s", day, keys, cfg.output_dir)
    client = NSEClient(cfg.base_url, cfg.network)
    storage = CsvStorage(cfg.output_dir)
    results = run_all([cfg.datasets[k] for k in keys], client, storage, day)
    return 0 if all(r.success for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
