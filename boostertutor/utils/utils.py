import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Union

import aiohttp
import imageio.v3 as iio
import numpy as np
import yaml
from parse import compile

logger = logging.getLogger(__name__)

SEALEDDECK_URL = "https://sealeddeck.tech/api/pools"
CUBECOBRA_URL = "https://cubecobra.com/cube/api/cubeJSON/"
EXCHANGE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
SET_SYMBOL_URL = (
    "https://gatherer.wizards.com/Handlers/Image.ashx?type=symbol&"
    "size={size}&rarity={rarity}&set={code}"
)
MTG_CARD_BACK = iio.imread("boostertutor/img/magic_back.webp")
A30_CARD_BACK = iio.imread("boostertutor/img/a30_back.webp")


@dataclass(frozen=True)
class Config:
    discord_token: str
    mtgjson_path: str
    set_img_path: Optional[str] = None
    command_prefix: str = "!"
    logging_level: Union[int, str] = logging.INFO
    validate_data: bool = True

    @staticmethod
    def from_file(path: Path = Path("config.yaml")) -> "Config":
        with open(path) as file:
            config_dict = yaml.load(file, Loader=yaml.FullLoader)
        config = Config(**config_dict)
        return config


async def pool_to_sealeddeck(
    pool: Sequence[dict], sealeddeck_id: Optional[str] = None
) -> str:
    """Upload a sealed pool to sealeddeck.tech and returns the id"""

    deck: dict[str, Union[Sequence[dict], str]] = {"sideboard": pool}
    if sealeddeck_id:
        deck["poolId"] = sealeddeck_id

    async with aiohttp.ClientSession() as session:
        async with session.post(SEALEDDECK_URL, json=deck) as resp:
            resp.raise_for_status()
            resp_json = await resp.json()

    return resp_json["poolId"]


def cards_img(
    im_list: Sequence[np.ndarray], max_row_length: int = 10
) -> np.ndarray:
    """Generate an image of the cards in im_list"""
    num_cards = len(im_list)
    assert num_cards
    num_rows = int(np.ceil(num_cards / max_row_length))  # type: ignore
    num_cards_per_row = int(np.ceil(num_cards / num_rows))  # type: ignore

    cards = None
    for row_i in range(num_rows):
        offset = row_i * num_cards_per_row
        row = im_list[offset]
        num_cards_this_row = min(num_cards - offset, num_cards_per_row)
        for i in range(1 + offset, num_cards_this_row + offset):
            row = np.hstack((row, im_list[i]))
        if cards is None:
            cards = row
        else:
            pad_amount = cards.shape[1] - row.shape[1]  # type: ignore
            assert pad_amount >= 0
            row = np.pad(
                row,
                [[0, 0], [0, pad_amount], [0, 0]],
                "constant",
                constant_values=255 if cards.shape[2] == 3 else 0,
            )
            cards = np.vstack((cards, row))
    return cards  # type: ignore


def card_backs_img(
    num_cards: int, max_row_length: int = 10, a30: bool = False
) -> np.ndarray:
    """Generate an image of num_cards Magic card backs"""
    assert num_cards > 0
    back_list = [A30_CARD_BACK if a30 else MTG_CARD_BACK] * num_cards
    return cards_img(back_list, max_row_length)


def arena_to_json(arena_list: str) -> Sequence[dict]:
    """Convert a list of cards in arena format to a list of json cards"""
    json_list = []
    p = compile("{count:d} {name} ({set}) {:d}")
    for line in arena_list.rstrip("\n ").split("\n"):
        card = p.parse(line)
        json_list.append(card.named)  # type: ignore
    return json_list


def set_symbol_link(code: str, size: str = "large", rarity: str = "M") -> str:
    return SET_SYMBOL_URL.format(size=size, rarity=rarity, code=code.lower())


async def get_eur_usd_rate() -> float:
    async with aiohttp.ClientSession() as session:
        async with session.get(EXCHANGE_URL) as resp:
            resp.raise_for_status()
            tree = ET.fromstring(await resp.read())
    for child in tree[2][0]:
        if child.attrib["currency"] == "USD":
            return float(child.attrib["rate"])
    logger.warning("EUR/USD exchange rate not found")
    return 1


async def get_cube(cube_id: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(CUBECOBRA_URL + cube_id) as resp:
            resp.raise_for_status()
            cube_json = await resp.json()
            return cube_json


def foil_layer(size: tuple[int, int]) -> np.ndarray:
    h, w = size
    ruler_w = np.linspace(-1, 1, w, endpoint=True)
    ruler_h = np.linspace(-1, 1, h, endpoint=True)
    _, Y = np.meshgrid(ruler_w, ruler_h)
    color_width, offset = 0.3, 0.0
    foil = np.empty((h, w, 3), dtype="uint8")
    foil[:, :, 0] = (
        (
            1
            - np.exp(
                -0.5 * ((Y - offset) ** 2) / (color_width * 3) ** 2
            )  # type: ignore
        )
        * 255
    ).astype("uint8")
    foil[:, :, 1] = (
        np.exp(-0.5 * ((Y - offset) ** 2) / color_width**2)  # type: ignore
        * 255
    ).astype("uint8")
    foil[:, :, 2] = (
        (1 - 1 / (1 + np.exp((Y - offset) / color_width)))  # type: ignore
        * 255
    ).astype("uint8")
    return foil
