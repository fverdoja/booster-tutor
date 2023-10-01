import argparse
from pathlib import Path

import requests

from boostertutor.utils.utils import Config, get_config

# configs
MTGJSON_URL = "https://mtgjson.com/api/v5/AllPrintings.json"


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
    backup_fp = Path(fp.parent, "AllPrintings_last.json")
    if backup and fp.is_file():
        fp.rename(backup_fp)
    try:
        download_file(url, fp)
    except requests.HTTPError as e:
        if backup and backup_fp.is_file():
            backup_fp.rename(fp)
        raise e


def main(config: Config) -> None:
    print(f"MTGjson data will be downloaded in: {config.mtgjson_path}")
    if Path(config.mtgjson_path).parent.is_dir():
        print("\nBeginning MTGjson data download...")
        download_mtgjson_data(file=config.mtgjson_path)
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
    config = get_config(args.config)

    main(config)
