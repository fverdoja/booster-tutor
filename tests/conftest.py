import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from boostertutor.generator import MtgPackGenerator
from boostertutor.models.mtg_card import MtgCard
from boostertutor.models.mtg_pack import MtgPack
from boostertutor.utils.utils import Config, get_config


@pytest.fixture(scope="session")
def generator() -> MtgPackGenerator:
    config = get_config()
    return MtgPackGenerator(
        path_to_mtgjson=config.mtgjson_path,
        path_to_jmp=config.jmp_decklists_path,
        jmp_arena=True,
    )


@pytest.fixture(scope="module")
def cards(generator: MtgPackGenerator) -> dict[str, MtgCard]:
    c19 = generator.data.sets["C19"].cards_by_ascii_name
    iko = generator.data.sets["IKO"].cards_by_ascii_name
    sta = generator.data.sets["STA"].cards_by_ascii_name
    return {
        "Ghostly Prison": MtgCard(c19["ghostly prison"]),  # uncommon
        "Clever Impersonator": MtgCard(c19["clever impersonator"]),  # mythic
        "Grim Haruspex": MtgCard(c19["grim haruspex"]),  # rare
        "Desperate Ravings": MtgCard(c19["desperate ravings"]),  # uncommon
        "Farseek": MtgCard(c19["farseek"]),  # common
        "Mysterious Egg": MtgCard(iko["mysterious egg"]),  # common, promo
        "Bojuka Bog": MtgCard(c19["bojuka bog"]),  # common land
        "Growing Ranks": MtgCard(c19["growing ranks"]),  # rare
        "Electrolyze": MtgCard(sta["electrolyze"], foil=True),  # rare foil
    }


@pytest.fixture
def four_set_list() -> list[str]:
    return ["MB1", "APC", "MIR", "AKR"]


@pytest.fixture
def unbalanced_pack(generator: MtgPackGenerator) -> MtgPack:
    m20 = generator.data.sets["M20"].cards_by_ascii_name
    content = {
        "basicOrCommonLand": {
            "cards": [MtgCard(m20["bloodfell caves"])],
            "balance": False,
        },
        "nonlandCommon": {
            "cards": [
                MtgCard(m20["thicket crasher"]),
                MtgCard(m20["destructive digger"]),
                MtgCard(m20["raise the alarm"]),
                MtgCard(m20["angelic gift"]),
                MtgCard(m20["ripscale predator"]),
                MtgCard(m20["inspiring captain"]),
                MtgCard(m20["bladebrand"]),
                MtgCard(m20["gorging vulture"]),
                MtgCard(m20["griffin protector"]),
                MtgCard(m20["act of treason"]),
            ],
            "backups": [MtgCard(m20["fortress crab"])],
            "balance": True,
        },
        "rareMythic": {
            "cards": [MtgCard(m20["thunderkin awakener"])],
            "balance": False,
        },
        "uncommon": {
            "cards": [
                MtgCard(m20["blightbeetle"]),
                MtgCard(m20["overcome"]),
                MtgCard(m20["herald of the sun"]),
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
        "shortID": "test_cube",
        "cards": [
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
                "tags": ["Non-foil"],
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
        ],
    }


@pytest.fixture
def zip_one() -> BytesIO:
    content = BytesIO()
    with ZipFile(content, "w") as zip:
        zip.writestr("deck1_JMP.json", json.dumps({"deck1": True}))
    content.seek(0)
    return content


@pytest.fixture
def zip_two() -> BytesIO:
    content = BytesIO()
    with ZipFile(content, "w") as zip:
        zip.writestr("deck2_JMP.json", json.dumps({"deck2": True}))
    content.seek(0)
    return content


@pytest.fixture
def temp_config(tmp_path: Path) -> Config:
    config_dict = {
        "discord_token": "0000",
        "imgur_client_id": "0000",
        "mtgjson_path": (tmp_path / "AllPrintings.json").as_posix(),
        "jmp_decklists_path": (tmp_path / "JMP/").as_posix(),
        "command_prefix": "!",
    }
    return Config(**config_dict)
