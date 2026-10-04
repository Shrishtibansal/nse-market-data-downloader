import pytest

from nse_downloader.exceptions import EmptyDataError, ValidationError
from nse_downloader.validation import validate
from tests.conftest import make_ds


def test_valid_data_passes():
    res = validate([{"symbol": "A", "ltp": 1}, {"symbol": "B", "ltp": 2}], make_ds())
    assert len(res.rows) == 2 and res.columns == ["symbol", "ltp"] and res.duplicates_removed == 0


def test_empty_rows_rejected():
    with pytest.raises(EmptyDataError):
        validate([], make_ds())


def test_missing_required_column_rejected():
    with pytest.raises(ValidationError, match="missing required"):
        validate([{"name": "A"}], make_ds())


def test_duplicates_removed_case_insensitively():
    rows = [{"symbol": "AAA"}, {"symbol": "aaa "}, {"symbol": "BBB"}]
    res = validate(rows, make_ds())
    assert [r["symbol"] for r in res.rows] == ["AAA", "BBB"]
    assert res.duplicates_removed == 1


def test_composite_dedupe_key_keeps_same_symbol_in_different_category():
    ds = make_ds(dedupe_keys=("category", "symbol"))
    rows = [{"category": "gainers", "symbol": "A"}, {"category": "losers", "symbol": "A"},
            {"category": "gainers", "symbol": "A"}]
    assert len(validate(rows, ds).rows) == 2


def test_blank_required_values_dropped():
    res = validate([{"symbol": "A"}, {"symbol": ""}, {"symbol": None}], make_ds())
    assert len(res.rows) == 1 and res.dropped_invalid == 2


def test_all_blank_is_rejected():
    with pytest.raises(EmptyDataError):
        validate([{"symbol": ""}], make_ds())
