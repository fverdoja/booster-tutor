import argparse
from pathlib import Path

import requests

from boostertutor.utils.utils import Config

# configs
MTGJSON_URL = "https://mtgjson.com/api/v5/AllPrintings.sqlite"


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
    temp_fp = Path(file + ".temp")
    backup_fp = Path(fp.parent, "AllPrintings_last.sqlite")
    try:
        download_file(url, temp_fp)
    except (requests.HTTPError, KeyboardInterrupt) as e:
        if temp_fp.exists():
            temp_fp.unlink()
        raise e
    if backup and fp.is_file():
        fp.rename(backup_fp)
    temp_fp.rename(fp)


def main(config: Config) -> None:
    print(f"MTGjson data will be downloaded in: {config.mtgjson_path}")
    if Path(config.mtgjson_path).parent.is_dir():
        print("\nBeginning MTGjson data download...")
        try:
            download_mtgjson_data(file=config.mtgjson_path)
        except KeyboardInterrupt:
            print(
                f"Aborted by user. File {config.mtgjson_path} untouched, and"
                "temporary file deleted."
            )
    else:
        print(
            f"The directory {Path(config.mtgjson_path).parent.as_posix()} "
            "does not exist."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Downloads MTGJSON data.")
    parser.add_argument(
        "--config",
        help="config file path (default: ./config.yaml)",
        default="config.yaml",
    )
    args = parser.parse_args()

    print("Reading config...")
    config = Config.from_file(args.config)

    main(config)
