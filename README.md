# NSE Market Data Downloader

Command-line pipeline that downloads four NSE market-data datasets and stores each as a dated CSV:
Top Gainers/Losers, Upper Band Hitters, Volume Gainers/Spurts, 52 Week High.

## Install
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run
```bash
python main.py                                  # all four datasets
python main.py --dataset top-gainers-losers     # one dataset
python main.py -d 52-week-high upper-band-hitters   # several
python main.py --list                           # show dataset keys
python main.py --output-dir ./my_csvs --log-level DEBUG
```
Exit code: `0` all OK, `1` at least one dataset failed, `2` config/usage error (useful for cron/CI alerts).

**Scheduling:** `scripts/crontab.example` (weekdays 16:00 IST, after market close). Docker: `docker build -t nse . && docker run -v $PWD/data:/data -v $PWD/logs:/app/logs nse`.

## How data acquisition works
nseindia.com pages are rendered from JSON endpoints, so we call those directly (no HTML scraping, no manual copying).
NSE rejects "cold" API calls, so the client first loads the home page to get cookies (like a browser), reuses that session,
and re-warms it on HTTP 401/403 or an empty body. Endpoints, query params, and the JSON path to the records live in
`config/datasets.yaml`:

| key | endpoint |
|---|---|
| top-gainers-losers | `/api/live-analysis-variations?index=gainers` and `?index=losers` (merged, `category` column added) |
| upper-band-hitters | `/api/live-analysis-price-band-hitter` |
| volume-gainers-spurts | `/api/live-analysis-volume-gainers` |
| 52-week-high | `/api/live-analysis-data-52weekhighstock` |

## Architecture
```
config/datasets.yaml   URLs + parsing rules (no URLs in code)
nse_downloader/
  client.py       acquisition: session, cookies, timeout, retry + exponential backoff with jitter
  parsers.py      JSON -> flat rows (configured path, auto-detect fallback)
  validation.py   non-empty, required columns, blank rows dropped, duplicates removed
  storage.py      atomic CSV writes, dated paths, idempotent
  pipeline.py     orchestration; each dataset isolated in its own try/except
  cli.py          argparse + wiring       main.py  entry point
```

## Where files are stored
`data/<dataset>/<dataset>_<YYYY-MM-DD>.csv`, e.g. `data/52-week-high/52-week-high_2026-10-05.csv`.
Date = IST calendar date. Change location with `--output-dir`, `NSE_OUTPUT_DIR`, or `output_dir` in the YAML.
Logs: console + `logs/nse_downloader.log` (rotating). Each line has timestamp, dataset, success/fail, record count, error.

## Error handling
- Timeout / connection error / HTTP 408, 425, 429, 5xx / non-JSON body / empty JSON: retried (default 3 retries, 1.5s -> 3s -> 6s, jittered).
- HTTP 401/403: session cookies reset, then retried.
- Other 4xx (e.g. 404): fail immediately, retrying won't help.
- Unexpected format: configured `data_path` missing -> warning + auto-detect largest list of records; none found -> `InvalidResponseError`.
- Validation failure (empty, missing columns): nothing is written, so a bad response can never overwrite a good file.
- A failure in one dataset is logged and the remaining datasets still run. Multi-request datasets are all-or-nothing (no half-gainers file).

## Duplicate handling
1. *Within a file:* rows are de-duplicated on `dedupe_keys` (case/whitespace-insensitive), count is logged.
2. *Across runs:* one file per dataset per day. Re-running the same day rewrites that same file atomically; if content is identical it logs `unchanged`.
   Latest snapshot of the day wins, since these are live pages and the end-of-day snapshot is the useful one.

## Tests
```bash
pip install -r requirements-dev.txt
pytest
```
Covers successful download, failed requests/retries/backoff, invalid + empty responses, validation, file creation, duplicate handling, failure isolation. No network needed (a fake session is injected).

## Limitations / assumptions
- NSE has **no official API**; endpoints are the ones its website uses and may change or block heavy use. If a dataset starts failing, run with `--log-level DEBUG` and adjust `config/datasets.yaml` (`endpoint`, `data_path`, `required_columns`).
- Required columns are intentionally minimal (`symbol`, plus `ltp` for gainers/losers); tighten them after checking real output.
- Filename date is the run date in IST, not the exchange's last trading date, so a weekend run is saved under that weekend date.
- - `sample_output/` contains real CSVs from a run on 2026-10-05, after market hours, so it reflects the last trading session.
- Only upper-band hitters are fetched (as the assignment asks); lower/both bands would be another config block.
