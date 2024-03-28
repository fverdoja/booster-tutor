from pathlib import Path

import imageio.v3 as iio

from boostertutor.utils.utils import Config, set_symbol_link

from ..generator import MtgPackGenerator


def main(
    local_path: Path,
    path_to_mtgjson: Path = Path("data/AllPrintings.sqlite"),
    size: str = "large",
    rarity: str = "M",
) -> None:
    if local_path.is_dir():
        print(f"Set images will be downloaded in: {local_path.as_posix()}")
        generator = MtgPackGenerator(
            path_to_mtgjson=path_to_mtgjson.as_posix()
        )
        for set_code in generator.sets_with_boosters:
            try:
                im = iio.imread(set_symbol_link(set_code, size, rarity))
                print(f"{set_code}\tOK")
                iio.imwrite(
                    (local_path / f"{set_code.lower()}.png").as_posix(), im
                )
            except OSError:
                print(f"{set_code}\tX")
    else:
        print(f"The directory {local_path.as_posix()} does not exist.")


if __name__ == "__main__":
    print("Reading config...")
    config = Config.from_file()
    if config.set_img_path:
        main(
            local_path=Path(config.set_img_path),
            path_to_mtgjson=Path(config.mtgjson_path),
        )
    else:
        print("Config does not contain set_img_path setting, doing nothing.")
