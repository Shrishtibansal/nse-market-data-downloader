import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def setup_logging(log_dir: Path | str = "logs", level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    for h in list(root.handlers):
        root.removeHandler(h)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(console)
    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(Path(log_dir) / "nse_downloader.log", maxBytes=1_000_000,
                                 backupCount=5, encoding="utf-8")
        fh.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(fh)
    except OSError as exc:  # logging to file is nice-to-have, not fatal
        root.warning("File logging disabled: %s", exc)
