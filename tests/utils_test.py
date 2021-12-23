from io import BytesIO
from typing import Optional

import boostertutor.utils.utils as utils
import imageio
import numpy as np
import pytest
from aioresponses import CallbackResult, aioresponses


@pytest.mark.parametrize("sealedpool_id", ["xxx", None])
async def test_pool_to_sealedpool(sealedpool_id: Optional[str]):
    pool = [{"name": "Opt", "count": 2}]

    def callback(url: str, **kargs):
        assert kargs["json"]["sideboard"] == pool
        assert kargs["json"].get("poolId", None) == sealedpool_id
        return CallbackResult(status=200, payload={"poolId": "yyy"})

    with aioresponses() as mocked:
        mocked.post(url=utils.SEALEDDECK_URL, callback=callback)
        pool_id = await utils.pool_to_sealeddeck(pool, sealedpool_id)
        assert pool_id == "yyy"


async def test_upload_img():
    client_id = "xxx"
    expected_link = "http://foo.url"
    img_file = BytesIO()
    imageio.imwrite(img_file, np.zeros((10, 10, 3)), format="jpeg")

    def callback(url: str, **kargs):
        assert kargs["data"]["image"] == img_file.getvalue()
        assert kargs["headers"]["Authorization"] == f"Client-ID {client_id}"
        return CallbackResult(
            status=200, payload={"data": {"link": expected_link}}
        )

    with aioresponses() as mocked:
        mocked.post(url=utils.IMGUR_URL, callback=callback)
        link = await utils.upload_img(img_file, client_id)
        assert link == expected_link


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
def test_cards_img(num_images: int, expected_shape: tuple[int, int, int]):
    card_list = [np.zeros((10, 10, 3)) for _ in range(num_images)]
    img = utils.cards_img(card_list)
    assert img.shape == expected_shape


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
def test_pack_img(num_images: int, expected_shape: tuple[int, int, int]):
    card_list = [np.zeros((10, 10, 3)) for _ in range(num_images)]
    img = utils.pack_img(card_list)
    assert img.shape == expected_shape


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
def test_rares_img(num_images: int, expected_shape: tuple[int, int, int]):
    card_list = [np.zeros((10, 10, 3)) for _ in range(num_images)]
    img = utils.rares_img(card_list)
    assert img.shape == expected_shape


def test_cards_pack_rares_img_empty():
    with pytest.raises(AssertionError):
        utils.cards_img([])
        utils.pack_img([])
        utils.rares_img([])


def test_arena_to_json():
    arena = "1 Opt (INV) 000\n3 Ponder (C18) 001\n "
    json_list = utils.arena_to_json(arena)
    assert json_list[0] == {"name": "Opt", "count": 1}
    assert json_list[1] == {"name": "Ponder", "count": 3}


def test_set_symbol_link():
    assert utils.set_symbol_link(code="INV", size="normal", rarity="C") == (
        "https://gatherer.wizards.com/Handlers/Image.ashx?"
        "type=symbol&size=normal&rarity=C&set=inv"
    )
