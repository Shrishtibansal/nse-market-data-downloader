import csv
from datetime import date

import pytest

from nse_downloader.exceptions import StorageError
from nse_downloader.storage import CsvStorage

DAY = date(2026, 10, 5)
ROWS = [{"symbol": "A", "ltp": 1}, {"symbol": "B", "ltp": 2}]
COLS = ["symbol", "ltp"]


def test_file_created_with_dataset_and_date_in_name(tmp_path):
    res = CsvStorage(tmp_path).save("52-week-high", ROWS, COLS, DAY)
    assert res.status == "created"
    assert res.path == tmp_path / "52-week-high" / "52-week-high_2026-10-05.csv"
    with open(res.path, newline="") as fh:
        assert list(csv.DictReader(fh)) == [{"symbol": "A", "ltp": "1"}, {"symbol": "B", "ltp": "2"}]


def test_second_identical_run_is_unchanged_and_makes_no_new_file(tmp_path):
    st = CsvStorage(tmp_path)
    st.save("d", ROWS, COLS, DAY)
    res = st.save("d", ROWS, COLS, DAY)
    assert res.status == "unchanged"
    assert len(list((tmp_path / "d").iterdir())) == 1


def test_changed_data_same_day_overwrites_same_file(tmp_path):
    st = CsvStorage(tmp_path)
    st.save("d", ROWS, COLS, DAY)
    res = st.save("d", ROWS + [{"symbol": "C", "ltp": 3}], COLS, DAY)
    assert res.status == "updated"
    assert len(list((tmp_path / "d").iterdir())) == 1       # no confusing duplicates
    assert "C,3" in res.path.read_text()


def test_different_day_gets_different_file(tmp_path):
    st = CsvStorage(tmp_path)
    st.save("d", ROWS, COLS, DAY)
    st.save("d", ROWS, COLS, date(2026, 10, 6))
    assert len(list((tmp_path / "d").iterdir())) == 2


def test_no_temp_files_left_behind(tmp_path):
    CsvStorage(tmp_path).save("d", ROWS, COLS, DAY)
    assert [p.name for p in (tmp_path / "d").iterdir()] == ["d_2026-10-05.csv"]


def test_unwritable_location_raises_storage_error(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")                      # a *file* where a directory is needed
    with pytest.raises(StorageError):
        CsvStorage(blocker).save("d", ROWS, COLS, DAY)
