from pathlib import Path

import imageio
import yaml

from ..generator import MtgPackGenerator

IMAGE_URL = (
    "https://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&"
    "size={size}&rarity={rarity}&set={code}"
)


def main(
    local_path: Path,
    path_to_mtgjson: Path = Path("data/AllPrintings.json"),
    size: str = "large",
    rarity: str = "M",
) -> None:
    if local_path.is_dir():
        print(f"Set images will be downloaded in: {local_path.as_posix()}")
        generator = MtgPackGenerator(
            path_to_mtgjson=path_to_mtgjson.as_posix()
        )
        for set in generator.sets_with_boosters:
            set = set.lower()
            try:
                im = imageio.imread(
                    IMAGE_URL.format(size=size, rarity=rarity, code=set)
                )
                print(f"{set}\tOK")
                imageio.imwrite((local_path / f"{set}.png").as_posix(), im)
            except ValueError:
                print(f"{set}\tX")
    else:
        print(f"The directory {local_path.as_posix()} does not exist.")


if __name__ == "__main__":
    print("Reading config...")

    with open("config.yaml") as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    main(
        local_path=Path(config["set_img_path"]),
        path_to_mtgjson=Path(config["mtgjson_path"]),
    )
