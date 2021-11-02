import pytest
import yaml
from boostertutor.generator import MtgPackGenerator
from boostertutor.models.mtg_card import MtgCard
from boostertutor.models.mtg_pack import MtgPack


@pytest.fixture(scope="session")
def generator():
    with open("config.yaml") as file:
        conf = yaml.load(file, Loader=yaml.FullLoader)
    jmp = conf["jmp_decklists_path"] if "jmp_decklists_path" in conf else None
    return MtgPackGenerator(
        path_to_mtgjson=conf["mtgjson_path"], path_to_jmp=jmp, jmp_arena=True
    )


@pytest.fixture
def four_set_list():
    return ["MB1", "APC", "MIR", "AKR"]


@pytest.fixture
def unbalanced_pack(generator):
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
