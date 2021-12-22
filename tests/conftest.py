import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml
from boostertutor.generator import MtgPackGenerator
from boostertutor.models.mtg_card import MtgCard
from boostertutor.models.mtg_pack import MtgPack


@pytest.fixture(scope="session")
def generator() -> MtgPackGenerator:
    with open("config.yaml") as file:
        conf = yaml.load(file, Loader=yaml.FullLoader)
    jmp = conf["jmp_decklists_path"] if "jmp_decklists_path" in conf else None
    return MtgPackGenerator(
        path_to_mtgjson=conf["mtgjson_path"], path_to_jmp=jmp, jmp_arena=True
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
def config_mock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def test_config(*args, **kargs):
        return {
            "discord_token": "0000",
            "imgur_client_id": "0000",
            "mtgjson_path": (tmp_path / "AllPrintings.json").as_posix(),
            "jmp_decklists_path": (tmp_path / "JMP/").as_posix(),
            "command_prefix": "!",
            "pack_logging": True,
        }

    monkeypatch.setattr(yaml, "load", test_config)
