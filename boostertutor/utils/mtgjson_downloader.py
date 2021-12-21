import argparse
import shutil
from pathlib import Path
from zipfile import ZipFile

import requests
import yaml

# configs
MTGJSON_URL = "https://mtgjson.com/api/v5/AllPrintings.json"
DECKFILE_URL = "https://mtgjson.com/api/v5/AllDeckFiles.zip"


def download_file(url: str, path: Path) -> None:
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with Path.open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def download_mtgjson_data(
    file: str, url: str = MTGJSON_URL, backup: bool = True
) -> None:
    fp = Path(file)
    if backup and fp.is_file():
        fp.rename(Path(fp.parent, "AllPrintings_last.json"))
    download_file(url, fp)


def download_jmp_decks(
    dir: str,
    temp_dir: str = ".",
    url: str = DECKFILE_URL,
    backup: bool = False,
) -> None:
    temp_path = Path(temp_dir) / "temp_decks"
    fn = "AllDeckFiles.zip"
    try:
        temp_path.mkdir(exist_ok=True)
        download_file(url, temp_path / fn)
        with ZipFile(temp_path / fn, "r") as zipObj:
            # Extract all the contents of zip file in current directory
            zipObj.extractall(temp_path)

        path = Path(dir)
        if backup and path.exists():
            if (path.parent / "JMP_last").exists():
                shutil.rmtree(path.parent / "JMP_last")
            path.rename(path.parent / "JMP_last")

        if not path.exists():
            path.mkdir()

        deck_path = path / "decks"
        deck_path.mkdir(exist_ok=True)
        for fp in temp_path.glob("*JMP.json"):
            fp.rename(Path(deck_path, fp.name))
    finally:
        shutil.rmtree(temp_path)


def main(jmp: bool, jmp_backup: bool) -> None:
    print("Reading config...")

    with open("config.yaml") as file:
        config = yaml.load(file, Loader=yaml.FullLoader)
    download_jmp = jmp and "jmp_decklists_path" in config

    print(f"MTGjson data will be downloaded in: {config['mtgjson_path']}")
    if download_jmp:
        print(
            f"JMP decks will be downloaded in: {config['jmp_decklists_path']}"
        )
        if jmp_backup:
            jmp_backup_path = (
                Path(config["jmp_decklists_path"]).parent / "JMP_last/"
            )
            print(
                f"Old JMP decks will be moved to: {jmp_backup_path.as_posix()}"
            )
    else:
        print("JMP deck will not be downloaded")

    print("\nBeginning MTGjson data download...")
    download_mtgjson_data(file=config["mtgjson_path"])

    if download_jmp:
        print("Beginning JMP decks download...")
        download_jmp_decks(
            dir=config["jmp_decklists_path"],
            temp_dir=Path(config["jmp_decklists_path"]).parent.as_posix(),
            backup=jmp_backup,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Downloads MTGJSON data.")
    parser.add_argument(
        "--jmp", help="download JMP decks", action="store_true"
    )
    parser.add_argument(
        "--jmp-backup", help="backup old JMP decks", action="store_true"
    )
    args = parser.parse_args()
    main(args.jmp, args.jmp_backup)
