import pytest

from nse_downloader.cli import main
from nse_downloader.config import load_config
from nse_downloader.exceptions import ConfigError


def test_real_config_has_all_four_datasets():
    cfg = load_config()
    assert set(cfg.datasets) == {"top-gainers-losers", "upper-band-hitters",
                                 "volume-gainers-spurts", "52-week-high"}


def test_output_dir_cli_overrides_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NSE_OUTPUT_DIR", "from_env")
    assert load_config(output_dir=tmp_path).output_dir == tmp_path
    assert str(load_config().output_dir) == "from_env"


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")


def test_list_and_unknown_dataset_exit_codes(tmp_path, capsys):
    assert main(["--list", "--log-dir", str(tmp_path)]) == 0
    assert "52-week-high" in capsys.readouterr().out
    assert main(["--dataset", "nonsense", "--log-dir", str(tmp_path)]) == 2
