import pytest

from nse_downloader.exceptions import InvalidResponseError
from nse_downloader.parsers import extract_records, flatten


def test_extract_with_configured_path():
    payload = {"upper": {"AllSec": {"data": [{"symbol": "A"}]}}}
    assert extract_records(payload, ("upper", "AllSec", "data")) == [{"symbol": "A"}]


def test_fallback_when_path_wrong_picks_largest_list():
    payload = {"meta": [{"x": 1}], "stuff": {"rows": [{"symbol": "A"}, {"symbol": "B"}]}}
    rows = extract_records(payload, ("data",))
    assert [r["symbol"] for r in rows] == ["A", "B"]


def test_no_records_anywhere_raises():
    with pytest.raises(InvalidResponseError):
        extract_records({"message": "nope"}, ("data",))


def test_non_json_type_raises():
    with pytest.raises(InvalidResponseError):
        extract_records("hello", ("data",))


def test_records_must_be_objects():
    with pytest.raises(InvalidResponseError):
        extract_records({"data": [1, 2]}, ("data",))


def test_flatten_nested():
    assert flatten({"a": 1, "m": {"b": 2, "n": {"c": 3}}, "l": [1, 2]}) == {"a": 1, "m_b": 2, "m_n_c": 3, "l": "1;2"}
