"""Acquisition layer: talks HTTP to NSE, nothing else.

NSE's JSON endpoints reject "cold" requests. A browser first loads the home
page (which sets cookies) and only then calls the API. We copy that: warm up
once, reuse the session, and re-warm if NSE answers 401/403 or an empty body.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Any, Callable

import requests

from .config import NetworkConfig
from .exceptions import FetchError

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
SESSION_RESET_STATUS = {401, 403}


class _Retryable(Exception):
    """Internal signal: this attempt failed but trying again may help."""


class NSEClient:
    def __init__(
        self,
        base_url: str,
        network: NetworkConfig,
        session: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.network = network
        self._session = session or requests.Session()
        self._sleep = sleep          # injectable -> tests don't actually wait
        self._rng = rng
        self._warmed = False

    # -- helpers ---------------------------------------------------------
    def _headers(self, api: bool) -> dict[str, str]:
        headers = {
            "User-Agent": self.network.user_agent,
            "Accept-Language": "en-US,en;q=0.9",
        }
        if api:
            headers["Accept"] = "application/json, text/plain, */*"
            headers["Referer"] = f"{self.base_url}/market-data/live-market-indices"
        else:
            headers["Accept"] = "text/html,application/xhtml+xml"
        return headers

    def _warm_up(self) -> None:
        log.debug("Warming up NSE session (collecting cookies)")
        self._session.get(self.base_url, headers=self._headers(api=False),
                          timeout=self.network.timeout_seconds)
        self._warmed = True

    def _reset_session(self) -> None:
        self._warmed = False
        cookies = getattr(self._session, "cookies", None)
        if cookies is not None:
            cookies.clear()

    def _backoff(self, attempt: int) -> float:
        n = self.network
        delay = min(n.max_backoff_seconds, n.initial_backoff_seconds * n.backoff_multiplier ** (attempt - 1))
        return delay * (0.5 + 0.5 * self._rng())   # jitter: 50-100% of delay

    # -- one attempt -----------------------------------------------------
    def _fetch_once(self, url: str, params: dict | None) -> Any:
        try:
            if not self._warmed:
                self._warm_up()
            resp = self._session.get(url, params=params, headers=self._headers(api=True),
                                     timeout=self.network.timeout_seconds)
        except requests.exceptions.Timeout as exc:
            raise _Retryable(f"timeout after {self.network.timeout_seconds}s") from exc
        except requests.exceptions.ConnectionError as exc:
            raise _Retryable(f"connection error: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise FetchError(f"request failed: {exc}") from exc

        status = resp.status_code
        if status in SESSION_RESET_STATUS:
            self._reset_session()
            raise _Retryable(f"HTTP {status} (session cookies refreshed)")
        if status in RETRYABLE_STATUS:
            raise _Retryable(f"HTTP {status}")
        if status >= 400:
            raise FetchError(f"HTTP {status} (not retryable)")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise _Retryable("response is not valid JSON (maybe a block/HTML page)") from exc
        if payload in (None, {}, []):
            self._reset_session()
            raise _Retryable("empty JSON payload")
        return payload

    # -- public ----------------------------------------------------------
    def get_json(self, endpoint: str, params: dict | None = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        attempts = self.network.max_retries + 1
        last: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                payload = self._fetch_once(url, params)
                log.debug("GET %s ok on attempt %d", endpoint, attempt)
                return payload
            except _Retryable as exc:
                last = exc
                log.warning("GET %s attempt %d/%d failed: %s", endpoint, attempt, attempts, exc)
                if attempt < attempts:
                    self._sleep(self._backoff(attempt))
        raise FetchError(f"GET {endpoint} failed after {attempts} attempts: {last}")
