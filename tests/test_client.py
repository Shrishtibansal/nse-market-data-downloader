import pytest

from nse_downloader.client import NSEClient
from nse_downloader.exceptions import FetchError
from tests.conftest import CONNERR, GOOD, TIMEOUT, FakeResponse, FakeSession

BASE = "https://www.nseindia.com"


def make(net, script):
    sleeps = []
    session = FakeSession(script)
    client = NSEClient(BASE, net, session=session, sleep=sleeps.append, rng=lambda: 1.0)
    return client, session, sleeps


def test_successful_download(net):
    client, session, sleeps = make(net, [FakeResponse(200, GOOD)])
    assert client.get_json("/api/x") == GOOD
    assert session.warmups == 1 and session.api_calls == 1 and sleeps == []


def test_session_is_warmed_only_once(net):
    client, session, _ = make(net, [FakeResponse(200, GOOD), FakeResponse(200, GOOD)])
    client.get_json("/api/x")
    client.get_json("/api/y")
    assert session.warmups == 1


def test_timeout_then_success_uses_exponential_backoff(net):
    client, session, sleeps = make(net, [TIMEOUT, CONNERR, FakeResponse(200, GOOD)])
    assert client.get_json("/api/x") == GOOD
    assert sleeps == [1.0, 2.0]          # 1 * 2^0, 1 * 2^1 (jitter fixed at 1.0)


def test_retries_exhausted_raises_fetch_error(net):
    client, session, _ = make(net, [TIMEOUT, TIMEOUT, TIMEOUT])
    with pytest.raises(FetchError, match="3 attempts"):
        client.get_json("/api/x")
    assert session.api_calls == 3


def test_http_500_is_retried(net):
    client, _, _ = make(net, [FakeResponse(500), FakeResponse(200, GOOD)])
    assert client.get_json("/api/x") == GOOD


def test_http_404_is_not_retried(net):
    client, session, sleeps = make(net, [FakeResponse(404)])
    with pytest.raises(FetchError, match="404"):
        client.get_json("/api/x")
    assert session.api_calls == 1 and sleeps == []


def test_403_refreshes_session_cookies(net):
    client, session, _ = make(net, [FakeResponse(403), FakeResponse(200, GOOD)])
    assert client.get_json("/api/x") == GOOD
    assert session.cookies.cleared == 1
    assert session.warmups == 2          # warmed again after reset


def test_invalid_json_is_retried_then_fails(net):
    bad = FakeResponse(200, text_body="<html>blocked</html>")
    client, _, _ = make(net, [bad, bad, bad])
    with pytest.raises(FetchError, match="not valid JSON"):
        client.get_json("/api/x")


def test_empty_payload_is_retried(net):
    client, _, _ = make(net, [FakeResponse(200, {}), FakeResponse(200, GOOD)])
    assert client.get_json("/api/x") == GOOD
