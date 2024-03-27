import dataclasses
from typing import Any, Optional

import numpy as np
import pytest
import yaml
from aiohttp import ClientResponseError
from aioresponses import CallbackResult, aioresponses

import boostertutor.utils.utils as utils


def test_get_config(
    monkeypatch: pytest.MonkeyPatch, temp_config: utils.Config
) -> None:
    def config_dict(*args: Any, **kargs: Any) -> dict[str, Any]:
        return dataclasses.asdict(temp_config)

    monkeypatch.setattr(yaml, "load", config_dict)
    config = utils.get_config()
    assert config.discord_token == "0000"
    assert config.mtgjson_path.endswith("AllPrintings.sqlite")
    assert config.set_img_path is None
    assert config.command_prefix == "!"
    assert config.logging_level == 20  # logging.INFO


def test_get_config_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_config(*args: Any, **kargs: Any) -> dict[str, str]:
        return {"discord_token": "0000"}

    monkeypatch.setattr(yaml, "load", missing_config)
    with pytest.raises(TypeError) as excinfo:
        utils.get_config()
    assert "missing 1 required positional argument: 'mtgjson_path'" in str(
        excinfo.value
    )


def test_get_config_wrong(monkeypatch: pytest.MonkeyPatch) -> None:
    def wrong_config(*args: Any, **kargs: Any) -> dict[str, str]:
        return {"diskord_token": "0000"}

    monkeypatch.setattr(yaml, "load", wrong_config)
    with pytest.raises(TypeError) as excinfo:
        utils.get_config()
    assert "unexpected keyword argument 'diskord_token'" in str(excinfo.value)


@pytest.mark.parametrize("sealedpool_id", ["xxx", None])
async def test_pool_to_sealedpool(sealedpool_id: Optional[str]) -> None:
    pool = [{"name": "Opt", "count": 2}]

    def callback(url: str, **kargs: Any) -> CallbackResult:
        assert kargs["json"]["sideboard"] == pool
        assert kargs["json"].get("poolId", None) == sealedpool_id
        return CallbackResult(status=200, payload={"poolId": "yyy"})

    with aioresponses() as mocked:
        mocked.post(url=utils.SEALEDDECK_URL, callback=callback)
        pool_id = await utils.pool_to_sealeddeck(pool, sealedpool_id)
        assert pool_id == "yyy"


@pytest.mark.parametrize(
    ["num_images", "expected_shape"],
    [
        (1, (10, 10, 3)),
        (3, (10, 30, 3)),
        (10, (10, 100, 3)),
        (11, (20, 60, 3)),
        (25, (30, 90, 3)),
    ],
)
def test_cards_img(
    num_images: int, expected_shape: tuple[int, int, int]
) -> None:
    card_list = [
        np.zeros((10, 10, 3), dtype="uint8") for _ in range(num_images)
    ]
    img = utils.cards_img(card_list)
    assert img.shape == expected_shape


@pytest.mark.parametrize(
    ["num_images", "max_row_length", "expected_shape"],
    [
        (1, 2, (10, 10, 3)),
        (2, 2, (10, 20, 3)),
        (3, 2, (20, 20, 3)),
        (4, 2, (20, 20, 3)),
        (5, 2, (30, 20, 3)),
    ],
)
def test_cards_img_max_row_length(
    num_images: int, max_row_length: int, expected_shape: tuple[int, int, int]
) -> None:
    card_list = [
        np.zeros((10, 10, 3), dtype="uint8") for _ in range(num_images)
    ]
    img = utils.cards_img(card_list, max_row_length)
    assert img.shape == expected_shape


def test_cards_img_empty() -> None:
    with pytest.raises(AssertionError):
        utils.cards_img([])


@pytest.mark.parametrize(
    ["num_images", "expected_shape"],
    [
        (1, (680, 488, 3)),
        (3, (680, 488 * 3, 3)),
        (10, (680, 488 * 10, 3)),
        (11, (680 * 2, 488 * 6, 3)),
        (25, (680 * 3, 488 * 9, 3)),
    ],
)
def test_card_backs_img(
    num_images: int, expected_shape: tuple[int, int, int]
) -> None:
    img = utils.card_backs_img(num_images)
    assert img.shape == expected_shape


@pytest.mark.parametrize(
    ["num_images", "max_row_length", "expected_shape"],
    [
        (1, 2, (680, 488, 3)),
        (2, 2, (680, 488 * 2, 3)),
        (3, 2, (680 * 2, 488 * 2, 3)),
        (4, 2, (680 * 2, 488 * 2, 3)),
        (5, 2, (680 * 3, 488 * 2, 3)),
    ],
)
def test_card_backs_img_max_row_length(
    num_images: int, max_row_length: int, expected_shape: tuple[int, int, int]
) -> None:
    img = utils.card_backs_img(num_images, max_row_length)
    assert img.shape == expected_shape


def test_card_backs_img_a30() -> None:
    default = utils.card_backs_img(1)
    mtg = utils.card_backs_img(1, a30=False)
    a30 = utils.card_backs_img(1, a30=True)
    assert (default == mtg).all()
    assert (default != a30).any()
    assert default.shape == a30.shape


def test_card_backs_img_empty() -> None:
    with pytest.raises(AssertionError):
        utils.card_backs_img(0)


def test_arena_to_json() -> None:
    arena = "1 Opt (INV) 000\n3 Ponder (C18) 001\n "
    json_list = utils.arena_to_json(arena)
    assert json_list[0] == {"name": "Opt", "count": 1, "set": "INV"}
    assert json_list[1] == {"name": "Ponder", "count": 3, "set": "C18"}


def test_set_symbol_link() -> None:
    assert utils.set_symbol_link(code="INV", size="normal", rarity="C") == (
        "https://gatherer.wizards.com/Handlers/Image.ashx?"
        "type=symbol&size=normal&rarity=C&set=inv"
    )


async def test_eur_usd_rate() -> None:
    exchange_xml = (
        "<root><zero /><one /><two><zero>"
        "<child currency='USD' rate='1.30'/>"
        "<child currency='JPY' rate='130.00'/>"
        "</zero></two></root>"
    )
    with aioresponses() as mocked:
        mocked.get(url=utils.EXCHANGE_URL, status=200, body=exchange_xml)
        rate = await utils.get_eur_usd_rate()
    assert rate == pytest.approx(1.3)


async def test_get_cube() -> None:
    cube1_id = "cube_one"
    cube1_json = {"name": "Cube 1"}
    cube2_id = "cube_two"
    cube2_json = {"name": "Cube 2"}
    cube3_id = "cube_three"
    with aioresponses() as mocked:
        mocked.get(
            url=utils.CUBECOBRA_URL + cube1_id, status=200, payload=cube1_json
        )
        mocked.get(
            url=utils.CUBECOBRA_URL + cube2_id, status=200, payload=cube2_json
        )
        mocked.get(url=utils.CUBECOBRA_URL + cube3_id, status=404)

        cube1 = await utils.get_cube(cube1_id)
        assert cube1["name"] == "Cube 1"
        cube2 = await utils.get_cube(cube2_id)
        assert cube2["name"] == "Cube 2"
        with pytest.raises(ClientResponseError):
            await utils.get_cube(cube3_id)


def test_foil_layer() -> None:
    foil = utils.foil_layer(size=(10, 20))
    assert foil.shape == (10, 20, 3)
    assert foil.dtype == np.uint8
