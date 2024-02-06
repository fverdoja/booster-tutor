import re
from io import BytesIO
from pathlib import Path
from typing import AsyncGenerator, Generator, TypeVar

import discord.ext.test as dpytest
import imageio
import numpy as np
import pytest
from aioresponses import CallbackResult, aioresponses
from discord import Intents

from boostertutor.bot import DiscordBot
from boostertutor.generator import MtgPackGenerator
from boostertutor.models.mtg_card import MtgCard
from boostertutor.models.mtg_pack import MtgPack
from boostertutor.utils.utils import (
    CUBECOBRA_URL,
    IMGUR_URL,
    SEALEDDECK_URL,
    Config,
    get_config,
)

T = TypeVar("T")

Yield = Generator[T, None, None]
AsyncYield = AsyncGenerator[T, None]


@pytest.fixture(scope="session")
def generator() -> MtgPackGenerator:
    config = get_config()
    return MtgPackGenerator(
        path_to_mtgjson=config.mtgjson_path, validate_data=False
    )


@pytest.fixture(scope="module")
def cards(generator: MtgPackGenerator) -> dict[str, MtgCard]:
    c19 = generator.data.sets["C19"]
    iko = generator.data.sets["IKO"]
    sta = generator.data.sets["STA"]
    bro = generator.data.sets["BRO"]
    return {
        "Ghostly Prison": MtgCard(
            c19.card_by_name("ghostly prison")  # type: ignore
        ),  # uncommon
        "Clever Impersonator": MtgCard(
            c19.card_by_name("clever impersonator")  # type: ignore
        ),  # mythic
        "Grim Haruspex": MtgCard(
            c19.card_by_name("grim haruspex")  # type: ignore
        ),  # rare
        "Desperate Ravings": MtgCard(
            c19.card_by_name("desperate ravings")  # type: ignore
        ),  # uncommon
        "Farseek": MtgCard(
            c19.card_by_name("farseek")  # type: ignore
        ),  # common
        "Mysterious Egg": MtgCard(
            iko.card_by_uuid(
                "5df3565b-ab85-5cc7-83c4-9cd3bb5674da"
            )  # type: ignore
        ),  # common, promo
        "Bojuka Bog": MtgCard(
            c19.card_by_name("bojuka bog")  # type: ignore
        ),  # common land
        "Growing Ranks": MtgCard(
            c19.card_by_name("growing ranks")  # type: ignore
        ),  # rare
        "Electrolyze": MtgCard(
            sta.card_by_uuid(
                "fd84e759-71d3-5168-8a2e-d664c45429f6"
            ),  # type: ignore
            foil=True,
        ),  # rare foil
        "Urza, Lord Protector": MtgCard(
            bro.card_by_name(
                "urza, lord protector // urza, planeswalker"
            )  # type: ignore
        ),  # mythic, meld top
        "The Mightstone and Weakstone": MtgCard(
            bro.card_by_name(
                "the mightstone and weakstone // urza, planeswalker"
            )  # type: ignore
        ),  # rare, meld bottom
    }


@pytest.fixture
def four_set_list() -> list[str]:
    return ["MB1", "APC", "MIR", "AKR"]


@pytest.fixture
def unbalanced_pack(generator: MtgPackGenerator) -> MtgPack:
    m20 = generator.data.sets["M20"]
    content = {
        "basicOrCommonLand": {
            "cards": [
                MtgCard(m20.card_by_name("bloodfell caves"))  # type: ignore
            ],
            "balance": False,
        },
        "nonlandCommon": {
            "cards": [
                MtgCard(m20.card_by_name("thicket crasher")),  # type: ignore
                MtgCard(
                    m20.card_by_name("destructive digger")  # type: ignore
                ),
                MtgCard(m20.card_by_name("raise the alarm")),  # type: ignore
                MtgCard(m20.card_by_name("angelic gift")),  # type: ignore
                MtgCard(m20.card_by_name("ripscale predator")),  # type: ignore
                MtgCard(m20.card_by_name("inspiring captain")),  # type: ignore
                MtgCard(m20.card_by_name("bladebrand")),  # type: ignore
                MtgCard(m20.card_by_name("gorging vulture")),  # type: ignore
                MtgCard(m20.card_by_name("griffin protector")),  # type: ignore
                MtgCard(m20.card_by_name("act of treason")),  # type: ignore
            ],
            "backups": [
                MtgCard(m20.card_by_name("fortress crab"))  # type: ignore
            ],
            "balance": True,
        },
        "rareMythic": {
            "cards": [
                MtgCard(
                    m20.card_by_name("thunderkin awakener")  # type: ignore
                )
            ],
            "balance": False,
        },
        "uncommon": {
            "cards": [
                MtgCard(m20.card_by_name("blightbeetle")),  # type: ignore
                MtgCard(m20.card_by_name("overcome")),  # type: ignore
                MtgCard(m20.card_by_name("herald of the sun")),  # type: ignore
            ],
            "balance": False,
        },
    }
    p = MtgPack(content)
    return p


@pytest.fixture
def cube() -> dict:
    return {
        "name": "Test Cube",
        "shortId": "test_cube",
        "cards": {
            "mainboard": [
                {
                    "cardID": "fb9cd7d9-8aad-4607-890c-9c8efe016a92",
                    "finish": "Non-foil",
                    "tags": ["Double"],
                },
                {
                    "cardID": "9797c813-0cda-44ad-ae41-330e9bde9cb9",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "a9d6bd19-77c9-4a1a-a2d5-6f9737693fea",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "e312653d-c3e1-4c79-90d2-0963419b618c",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "c1718028-3009-4bdd-9f6f-59c17edd1344",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "f3da5010-78b6-426f-aeb4-73c21d2af581",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "868efcee-bb13-4b6f-b81b-99408685e4c4",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "c12529e4-f4b1-45be-8252-28783badbec5",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "9621f341-bf85-4b77-bf19-2fb013b4c955",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "39514d54-cb6c-4b3b-a3be-46db991be4d4",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "3a4d395e-d7d6-4e93-9761-b0bae63b7b1c",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "54c76a22-f9e3-408b-a5bd-403add57e31a",
                    "finish": "Non-foil",
                    "tags": ["Non-foil"],
                },
                {
                    "cardID": "35b3da05-9a3e-4827-96b8-5de244128db3",
                    "finish": "Non-foil",
                    "tags": [],
                },
                {
                    "cardID": "a7af8350-9a51-437c-a55e-19f3e07acfa9",
                    "finish": "Etched",
                    "tags": ["Etched"],
                },
                {
                    "cardID": "39dce974-846f-4365-b0a5-851e38668e7d",
                    "finish": "Foil",
                    "tags": ["Foil"],
                },
            ]
        },
    }


@pytest.fixture
def card_img_file() -> BytesIO:
    img_file = BytesIO()
    imageio.imwrite(img_file, np.zeros((10, 10, 3)), format="jpeg")
    return img_file


@pytest.fixture
def temp_config(tmp_path: Path) -> Config:
    config_dict = {
        "discord_token": "0000",
        "imgur_client_id": "0000",
        "mtgjson_path": (tmp_path / "AllPrintings.sqlite").as_posix(),
        "command_prefix": "!",
        "validate_data": False,
    }
    return Config(**config_dict)  # type: ignore


@pytest.fixture
def mocked_aioresponses(cube: dict, card_img_file: BytesIO) -> Yield[None]:
    pattern = re.compile(r"^https://api\.scryfall\.com/cards.*$")

    def imgur_callback(url: str, **kargs):
        return CallbackResult(
            status=200, payload={"data": {"link": "http://foo.url"}}
        )

    def sealeddeck_callback(url: str, **kargs):
        return CallbackResult(status=200, payload={"poolId": "yyy"})

    with aioresponses() as mocked:
        mocked.post(url=IMGUR_URL, callback=imgur_callback)
        mocked.post(url=SEALEDDECK_URL, callback=sealeddeck_callback)
        mocked.get(url=CUBECOBRA_URL + "mocked_cube", status=200, payload=cube)
        mocked.get(url=CUBECOBRA_URL + "non_existent_cube", status=404)
        mocked.get(
            url=pattern, status=200, body=card_img_file.getvalue(), repeat=True
        )
        yield


@pytest.fixture
async def bot(
    temp_config: Config, generator: MtgPackGenerator
) -> AsyncYield[DiscordBot]:
    intents = Intents.default()
    intents.members = True
    bot = DiscordBot(temp_config, generator, intents=intents)
    dpytest.configure(bot)

    yield bot

    # Teardown
    await dpytest.empty_queue()  # empty global message queue as test teardown


def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    """Code to execute after all tests."""

    # dat files are created by dpytest when using attachements
    print("\n-------------------------\nClean dpytest_*.dat files")
    dat_files = Path(".").glob("dpytest_*.dat")
    for file_path in dat_files:
        try:
            file_path.unlink()
        except Exception:
            print("Error while deleting file : ", file_path)
