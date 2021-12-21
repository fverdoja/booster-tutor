import json
from io import BytesIO
from pathlib import Path

import pytest
from boostertutor.utils import mtgjson_downloader
from requests_mock import Mocker


def test_download_file(tmp_path: Path, requests_mock: Mocker):
    requests_mock.get("http://foo.bar", json={"ok": True})
    tmp_file = tmp_path / "file.json"
    mtgjson_downloader.download_file(url="http://foo.bar", path=tmp_file)
    assert tmp_file.is_file()


@pytest.mark.parametrize("backup", [False, True])
def test_download_mtgjson_data(
    tmp_path: Path, requests_mock: Mocker, backup: bool
):
    mtgjson_file = tmp_path / "AllPrintings.json"
    backup_file = tmp_path / "AllPrintings_last.json"

    requests_mock.get(mtgjson_downloader.MTGJSON_URL, json={"first": True})
    mtgjson_downloader.download_mtgjson_data(
        file=mtgjson_file.as_posix(), backup=False
    )
    assert mtgjson_file.is_file()
    assert not backup_file.exists()

    requests_mock.get(mtgjson_downloader.MTGJSON_URL, json={"second": True})
    mtgjson_downloader.download_mtgjson_data(
        file=mtgjson_file.as_posix(), backup=backup
    )
    assert mtgjson_file.is_file()
    assert backup_file.is_file() == backup
    with open(mtgjson_file) as f:
        assert json.load(f)["second"]
    if backup:
        with open(backup_file) as f:
            assert json.load(f)["first"]


@pytest.mark.parametrize("backup", [False, True])
def test_download_jmp_decks(
    tmp_path: Path,
    requests_mock: Mocker,
    zip_one: BytesIO,
    zip_two: BytesIO,
    backup: bool,
):
    jmp_dir = tmp_path / "JMP"
    backup_dir = tmp_path / "JMP_last"
    temp_dir = tmp_path / "temp_decks"

    requests_mock.get(mtgjson_downloader.DECKFILE_URL, body=zip_one)
    mtgjson_downloader.download_jmp_decks(
        dir=jmp_dir.as_posix(), temp_dir=tmp_path.as_posix(), backup=False
    )
    assert not temp_dir.exists()
    assert (jmp_dir / "decks" / "deck1_JMP.json").is_file()
    assert not backup_dir.exists()

    requests_mock.get(mtgjson_downloader.DECKFILE_URL, body=zip_two)
    mtgjson_downloader.download_jmp_decks(
        dir=jmp_dir.as_posix(), temp_dir=tmp_path.as_posix(), backup=backup
    )
    assert not temp_dir.exists()
    assert (jmp_dir / "decks" / "deck2_JMP.json").is_file()
    assert (backup_dir / "decks" / "deck1_JMP.json").is_file() == backup
    with open(jmp_dir / "decks" / "deck2_JMP.json") as f:
        assert json.load(f)["deck2"]
    if backup:
        with open(backup_dir / "decks" / "deck1_JMP.json") as f:
            assert json.load(f)["deck1"]


@pytest.mark.parametrize(
    ["jmp", "jmp_backup"], [(False, False), (True, False), (True, True)]
)
@pytest.mark.usefixtures("config_mock")
def test_mtgjson_downloader_main(
    tmp_path: Path,
    requests_mock: Mocker,
    zip_one: BytesIO,
    jmp: bool,
    jmp_backup: bool,
):
    mtgjson_file = tmp_path / "AllPrintings.json"
    backup_file = tmp_path / "AllPrintings_last.json"
    jmp_dir = tmp_path / "JMP"
    backup_dir = tmp_path / "JMP_last"
    temp_dir = tmp_path / "temp_decks"

    with open(mtgjson_file, "w") as f:
        json.dump({"first": True}, f)
    if jmp_backup:
        jmp_dir.mkdir()

    requests_mock.get(mtgjson_downloader.MTGJSON_URL, json={"second": True})
    requests_mock.get(mtgjson_downloader.DECKFILE_URL, body=zip_one)
    mtgjson_downloader.main(jmp=jmp, jmp_backup=jmp_backup)
    assert mtgjson_file.is_file()
    assert backup_file.is_file()
    with open(mtgjson_file) as f:
        assert json.load(f)["second"]
    with open(backup_file) as f:
        assert json.load(f)["first"]
    assert not temp_dir.exists()
    assert jmp_dir.exists() == jmp
    assert backup_dir.exists() == jmp_backup
