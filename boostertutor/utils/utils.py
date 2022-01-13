import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional, Sequence, Union

import aiohttp
import numpy as np
import yaml

logger = logging.getLogger(__name__)

SEALEDDECK_URL = "https://sealeddeck.tech/api/pools"
IMGUR_URL = "https://api.imgur.com/3/image"
EXCHANGE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


@dataclass(frozen=True)
class Config:
    discord_token: str
    imgur_client_id: str
    mtgjson_path: str
    jmp_decklists_path: Optional[str] = None
    set_img_path: Optional[str] = None
    command_prefix: str = "!"
    logging_level: Union[int, str] = logging.INFO


def get_config(path: Path = Path("config.yaml")) -> Config:
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


async def upload_img(file: BytesIO, imgur_client_id: str) -> str:
    """Upload an image file to imgur.com and returns the link"""

    headers = {"Authorization": f"Client-ID {imgur_client_id}"}
    payload = {"image": file.getvalue()}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            IMGUR_URL, headers=headers, data=payload
        ) as resp:
            resp.raise_for_status()
            resp_json = await resp.json()

    return resp_json["data"]["link"]


def cards_img(
    im_list: Sequence[np.ndarray], max_row_length: int = 10
) -> np.ndarray:
    """Generate an image of the cards in im_list"""
    assert len(im_list)
    num_rows = int(np.ceil(len(im_list) / max_row_length))
    cards_per_row = int(np.ceil(len(im_list) / num_rows))

    cards = None
    for row_i in range(num_rows):
        offset = row_i * cards_per_row
        row = im_list[offset]
        num_cards = min(len(im_list) - offset, cards_per_row)
        for i in range(1 + offset, num_cards + offset):
            row = np.hstack((row, im_list[i]))
        if cards is None:
            cards = row
        else:
            pad_amount = cards.shape[1] - row.shape[1]
            assert pad_amount >= 0
            row = np.pad(
                row,
                [[0, 0], [0, pad_amount], [0, 0]],
                "constant",
                constant_values=255,
            )
            cards = np.vstack((cards, row))
    return cards


def pack_img(im_list: Sequence[np.ndarray]) -> np.ndarray:
    """Generate an image of the cards in a pack"""
    return cards_img(im_list)


def rares_img(im_list: Sequence[np.ndarray]) -> np.ndarray:
    """Generate an image of the rares in a sealed pool"""
    return cards_img(im_list)


def arena_to_json(arena_list: str) -> Sequence[dict]:
    """Convert a list of cards in arena format to a list of json cards"""
    json_list = []
    for line in arena_list.rstrip("\n ").split("\n"):
        count, card = line.split(" ", 1)
        card_name = card.split(" (")[0]
        json_list.append({"name": f"{card_name}", "count": int(count)})
    return json_list


def set_symbol_link(code: str, size: str = "large", rarity: str = "M") -> str:
    return (
        f"https://gatherer.wizards.com/Handlers/Image.ashx?"
        f"type=symbol&size={size}&rarity={rarity}&set={code.lower()}"
    )


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
