from pathlib import Path
from typing import Any

import numpy as np
import pytest
from requests import HTTPError
from requests_mock import Mocker

from boostertutor.utils import mtgjson_downloader, set_symbols_downloader
from boostertutor.utils.utils import Config


def test_download_file(tmp_path: Path, requests_mock: Mocker) -> None:
    requests_mock.get("http://foo.bar", text="CONTENT")
    tmp_file = tmp_path / "file"
    mtgjson_downloader.download_file(url="http://foo.bar", path=tmp_file)
    assert tmp_file.is_file()


def test_download_file_400(tmp_path: Path, requests_mock: Mocker) -> None:
    requests_mock.get("http://foo.bar", status_code=400)
    tmp_file = tmp_path / "file"
    with pytest.raises(HTTPError):
        mtgjson_downloader.download_file(url="http://foo.bar", path=tmp_file)
    assert not tmp_file.exists()


@pytest.mark.parametrize("backup", [False, True])
def test_download_mtgjson_data(
    tmp_path: Path, requests_mock: Mocker, backup: bool
) -> None:
    mtgjson_file = tmp_path / "AllPrintings.sqlite"
    backup_file = tmp_path / "AllPrintings_last.sqlite"

    requests_mock.get(mtgjson_downloader.MTGJSON_URL, text="FIRST")
    mtgjson_downloader.download_mtgjson_data(
        file=mtgjson_file.as_posix(), backup=False
    )
    assert mtgjson_file.is_file()
    assert not backup_file.exists()

    requests_mock.get(mtgjson_downloader.MTGJSON_URL, text="SECOND")
    mtgjson_downloader.download_mtgjson_data(
        file=mtgjson_file.as_posix(), backup=backup
    )
    assert mtgjson_file.is_file()
    assert backup_file.is_file() == backup
    with open(mtgjson_file) as f:
        assert f.read() == "SECOND"
    if backup:
        with open(backup_file) as f:
            assert f.read() == "FIRST"


@pytest.mark.parametrize("backup", [False, True])
def test_download_mtgjson_data_400(
    tmp_path: Path, requests_mock: Mocker, backup: bool
) -> None:
    mtgjson_file = tmp_path / "AllPrintings.sqlite"
    backup_file = tmp_path / "AllPrintings_last.sqlite"
    with open(mtgjson_file, "w") as f:
        f.write("FIRST")

    requests_mock.get(mtgjson_downloader.MTGJSON_URL, status_code=400)
    with pytest.raises(HTTPError):
        mtgjson_downloader.download_mtgjson_data(
            file=mtgjson_file.as_posix(), backup=backup
        )
    assert mtgjson_file.exists()
    assert not backup_file.exists()
    with open(mtgjson_file) as f:
        assert f.read() == "FIRST"


def test_mtgjson_downloader_main(
    tmp_path: Path,
    requests_mock: Mocker,
    temp_config: Config,
) -> None:
    mtgjson_file = tmp_path / "AllPrintings.sqlite"
    backup_file = tmp_path / "AllPrintings_last.sqlite"

    with open(mtgjson_file, "w") as f:
        f.write("FIRST")

    requests_mock.get(mtgjson_downloader.MTGJSON_URL, text="SECOND")
    mtgjson_downloader.main(config=temp_config)
    assert mtgjson_file.is_file()
    assert backup_file.is_file()
    with open(mtgjson_file) as f:
        assert f.read() == "SECOND"
    with open(backup_file) as f:
        assert f.read() == "FIRST"


def test_set_symbols_downloader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def im(*args: Any, **kargs: Any) -> np.ndarray:
        return np.zeros((10, 10, 3), dtype="uint8")

    def generator_init(
        self: set_symbols_downloader.MtgPackGenerator, *args: Any, **kargs: Any
    ) -> None:
        self.sets_with_boosters = ["FOO", "Bar"]

    monkeypatch.setattr(
        set_symbols_downloader.MtgPackGenerator, "__init__", generator_init
    )
    monkeypatch.setattr(set_symbols_downloader.iio, "imread", im)
    set_symbols_downloader.main(local_path=tmp_path)
    assert (tmp_path / "foo.png").is_file()
    assert (tmp_path / "bar.png").is_file()


def test_set_symbols_downloader_400(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def exept(*args: Any, **kargs: Any) -> None:
        raise OSError

    def generator_init(
        self: set_symbols_downloader.MtgPackGenerator, *args: Any, **kargs: Any
    ) -> None:
        self.sets_with_boosters = ["FOO", "Bar"]

    monkeypatch.setattr(
        set_symbols_downloader.MtgPackGenerator, "__init__", generator_init
    )
    monkeypatch.setattr(set_symbols_downloader.iio, "imread", exept)
    set_symbols_downloader.main(local_path=tmp_path)
    assert not (tmp_path / "foo.png").exists()
    assert not (tmp_path / "bar.png").exists()
