import pytest
import yaml
from boostertutor.generator import MtgPackGenerator


@pytest.fixture(scope="session")
def generator():
    with open("config.yaml") as file:
        config = yaml.load(file, Loader=yaml.FullLoader)
    jmp = config["jmp_decklists_path"] if "jmp_decklists_path" in config else None
    return MtgPackGenerator(path_to_mtgjson=config["mtgjson_path"],
                            path_to_jmp=jmp, jmp_arena=True)
