from pathlib import Path

import imageio
import yaml

from .. import bot

IMAGE_URL = (
    "https://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&"
    "size={size}&rarity={rarity}&set={code}"
)


def main(local_path: Path, size: str = "large", rarity: str = "M") -> None:
    if local_path.is_dir():
        print(f"Set images will be downloaded in: {local_path.as_posix()}")

        for set in bot.all_sets:
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

    main(Path(config["set_img_path"]))
