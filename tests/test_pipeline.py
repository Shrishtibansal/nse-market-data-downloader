import requests

from nse_downloader.config import RequestSpec
from nse_downloader.exceptions import FetchError
from nse_downloader.pipeline import run_all, run_dataset
from nse_downloader.storage import CsvStorage
from tests.conftest import FakeClient, make_ds

from datetime import date

DAY = date(2026, 10, 5)


def datasets():
    return [
        make_ds("a", requests=(RequestSpec("/a"),)),
        make_ds("b", requests=(RequestSpec("/b"),)),
        make_ds("c", requests=(RequestSpec("/c"),)),
    ]


def test_one_failure_does_not_block_the_others(tmp_path):
    client = FakeClient({
        "/a": {"data": [{"symbol": "A"}]},
        "/b": FetchError("network down"),
        "/c": {"data": [{"symbol": "C"}]},
    })
    results = run_all(datasets(), client, CsvStorage(tmp_path), DAY)
    assert [r.success for r in results] == [True, False, True]
    assert "network down" in results[1].error
    assert (tmp_path / "a" / "a_2026-10-05.csv").exists()
    assert not (tmp_path / "b").exists()
    assert (tmp_path / "c" / "c_2026-10-05.csv").exists()


def test_invalid_and_empty_responses_fail_cleanly_without_files(tmp_path):
    client = FakeClient({"/a": {"data": []}, "/b": {"message": "unexpected"}, "/c": ["not", "dicts"]})
    results = run_all(datasets(), client, CsvStorage(tmp_path), DAY)
    assert not any(r.success for r in results)
    assert list(tmp_path.iterdir()) == []


def test_unexpected_bug_is_contained(tmp_path):
    class Boom:
        def get_json(self, *a, **k):
            raise RuntimeError("bug")
    r = run_dataset(make_ds(), Boom(), CsvStorage(tmp_path), DAY)
    assert not r.success and "unexpected" in r.error


def test_running_twice_same_day_creates_no_duplicate_files(tmp_path):
    client = FakeClient({"/a": {"data": [{"symbol": "A"}, {"symbol": "A"}]}})
    ds = make_ds("a", requests=(RequestSpec("/a"),))
    first = run_dataset(ds, client, CsvStorage(tmp_path), DAY)
    second = run_dataset(ds, client, CsvStorage(tmp_path), DAY)
    assert first.file_status == "created" and first.records == 1 and first.duplicates_removed == 1
    assert second.file_status == "unchanged"
    assert len(list((tmp_path / "a").iterdir())) == 1


def test_multi_request_dataset_is_merged_with_tag_column(tmp_path):
    ds = make_ds("tgl", requests=(RequestSpec("/v", {"index": "gainers"}, "gainers"),
                                  RequestSpec("/v", {"index": "losers"}, "losers")),
                 tag_column="category", dedupe_keys=("category", "symbol"))
    client = FakeClient({
        ("/v", (("index", "gainers"),)): {"data": [{"symbol": "UP"}]},
        ("/v", (("index", "losers"),)): {"data": [{"symbol": "DOWN"}]},
    })
    r = run_dataset(ds, client, CsvStorage(tmp_path), DAY)
    assert r.success and r.records == 2
    text = r.path.read_text()
    assert "gainers,UP" in text and "losers,DOWN" in text


def test_partial_multi_request_failure_saves_nothing(tmp_path):
    ds = make_ds("tgl", requests=(RequestSpec("/v", {"index": "gainers"}, "gainers"),
                                  RequestSpec("/v", {"index": "losers"}, "losers")))
    client = FakeClient({
        ("/v", (("index", "gainers"),)): {"data": [{"symbol": "UP"}]},
        ("/v", (("index", "losers"),)): FetchError("boom"),
    })
    r = run_dataset(ds, client, CsvStorage(tmp_path), DAY)
    assert not r.success and not (tmp_path / "tgl").exists()
