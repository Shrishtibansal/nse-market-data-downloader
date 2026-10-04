import json
from pathlib import Path

import pytest
import requests

from nse_downloader.config import DatasetConfig, NetworkConfig, RequestSpec


class FakeResponse:
    def __init__(self, status=200, payload=None, text_body=None):
        self.status_code = status
        self._payload = payload
        self._text = text_body

    def json(self):
        if self._text is not None:
            raise ValueError("not json")
        return self._payload


class FakeCookies:
    def __init__(self):
        self.cleared = 0

    def clear(self):
        self.cleared += 1


class FakeSession:
    """Plays back a scripted list of responses/exceptions for API calls.
    The home-page warm-up call always succeeds."""

    def __init__(self, script):
        self.script = list(script)
        self.api_calls = 0
        self.warmups = 0
        self.cookies = FakeCookies()

    def get(self, url, params=None, headers=None, timeout=None):
        if url.rstrip("/").endswith("nseindia.com"):
            self.warmups += 1
            return FakeResponse(200, payload={"ok": 1})
        self.api_calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    """Stands in for NSEClient in pipeline tests: endpoint -> payload or Exception."""

    def __init__(self, routes):
        self.routes = routes

    def get_json(self, endpoint, params=None):
        key = (endpoint, tuple(sorted((params or {}).items())))
        value = self.routes.get(key, self.routes.get(endpoint))
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture
def net():
    return NetworkConfig(timeout_seconds=1, max_retries=2, initial_backoff_seconds=1,
                         backoff_multiplier=2, max_backoff_seconds=10)


def make_ds(key="volume-gainers-spurts", **kw):
    defaults = dict(
        key=key, name=key, page_url="",
        requests=(RequestSpec("/api/x"),),
        data_path=("data",), required_columns=("symbol",), dedupe_keys=("symbol",), tag_column=None,
    )
    defaults.update(kw)
    return DatasetConfig(**defaults)


@pytest.fixture
def ds():
    return make_ds()


GOOD = {"data": [{"symbol": "AAA", "ltp": 10.5}, {"symbol": "BBB", "ltp": 20}]}
TIMEOUT = requests.exceptions.Timeout("slow")
CONNERR = requests.exceptions.ConnectionError("down")
