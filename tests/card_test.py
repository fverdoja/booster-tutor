from contextlib import nullcontext as does_not_raise
from io import BytesIO
from typing import ContextManager, Optional, Sequence

import imageio
import numpy as np
import pytest
from aioresponses import aioresponses
from boostertutor.models.mtg_card import MtgCard
from aiohttp import ClientResponseError


@pytest.mark.parametrize(
    ["card", "expected"],
    [
        ("Ghostly Prison", ["W"]),
        ("Clever Impersonator", ["U"]),
        ("Grim Haruspex", ["B"]),
        ("Desperate Ravings", ["R"]),
        ("Farseek", ["G"]),
        ("Mysterious Egg", []),
        ("Bojuka Bog", []),
        ("Growing Ranks", ["WG"]),
        ("Electrolyze", ["U", "R"]),
    ],
)
def test_colors(cards: dict[str, MtgCard], card: str, expected: Sequence[str]):
    assert cards[card].mana() == expected


@pytest.mark.parametrize(
    ["card", "expected"],
    [
        ("Ghostly Prison", {"name": "Ghostly Prison", "count": 1}),
        ("Clever Impersonator", {"name": "Clever Impersonator", "count": 1}),
        ("Grim Haruspex", {"name": "Grim Haruspex", "count": 1}),
        ("Desperate Ravings", {"name": "Desperate Ravings", "count": 1}),
        ("Farseek", {"name": "Farseek", "count": 1}),
        ("Mysterious Egg", {"name": "Mysterious Egg", "count": 1}),
        ("Bojuka Bog", {"name": "Bojuka Bog", "count": 1}),
        ("Growing Ranks", {"name": "Growing Ranks", "count": 1}),
        ("Electrolyze", {"name": "Electrolyze", "count": 1}),
    ],
)
def test_json(cards: dict[str, MtgCard], card: str, expected: dict):
    assert cards[card].json() == expected


@pytest.mark.parametrize(
    ["card", "expected"],
    [
        ("Ghostly Prison", "1 Ghostly Prison (C19) 64"),
        ("Clever Impersonator", "1 Clever Impersonator (C19) 82"),
        ("Grim Haruspex", "1 Grim Haruspex (C19) 118"),
        ("Desperate Ravings", "1 Desperate Ravings (C19) 137"),
        ("Farseek", "1 Farseek (C19) 165"),
        ("Bojuka Bog", "1 Bojuka Bog (C19) 232"),
        ("Growing Ranks", "1 Growing Ranks (C19) 193"),
        ("Electrolyze", "1 Electrolyze (STA) 123"),
    ],
)
def test_arena(cards: dict[str, MtgCard], card: str, expected: str):
    assert cards[card].arena_format() == expected


def test_arena_promo(cards: dict[str, MtgCard]):
    promo = cards["Mysterious Egg"]
    assert promo.card.number == "385"  # check that it's the promo version
    assert promo.arena_format() == "1 Mysterious Egg (IKO) 3"


def test_pack_sort_key(cards: dict[str, MtgCard]):
    card_list = list(cards.values())
    card_list.sort(key=lambda x: x.pack_sort_key())
    names = [card.card.name for card in card_list]
    assert names == [
        "Clever Impersonator",
        "Grim Haruspex",
        "Growing Ranks",
        "Ghostly Prison",
        "Desperate Ravings",
        "Farseek",
        "Mysterious Egg",
        "Electrolyze",
        "Bojuka Bog",
    ]


@pytest.mark.parametrize(
    ["size", "foil", "expected_shape", "expected_raise"],
    [
        ("large", None, (936, 672, 3), does_not_raise()),
        ("normal", False, (680, 488, 3), does_not_raise()),
        ("small", True, (204, 146, 3), does_not_raise()),
        ("wrong_size", None, (1, 1, 1), pytest.raises(AssertionError)),
    ],
)
async def test_image(
    cards: dict[str, MtgCard],
    size: str,
    foil: Optional[bool],
    expected_shape: tuple[int, int, int],
    expected_raise: ContextManager,
):
    c = cards["Electrolyze"]  # foil card, produces a foil image by default
    scry_id = c.card.identifiers["scryfallId"]
    img_url = (
        f"https://api.scryfall.com/cards/{scry_id}"
        f"?format=image&version={size}"
    )
    expected_img = np.zeros(expected_shape)
    mock_img_file = BytesIO()
    imageio.imwrite(mock_img_file, expected_img, format="jpeg")
    with aioresponses() as mocked:
        mocked.get(url=img_url, status=200, body=mock_img_file.getvalue())
        with expected_raise:
            img = await c.get_image(size, foil)

            # if None or foil, the image should have been applied a foil
            # effect, so it should not match the original image
            expected_equal = not foil if foil is not None else False

            assert img.shape == expected_shape
            assert np.array_equal(img, expected_img) == expected_equal


async def test_image_400(cards: dict[str, MtgCard]):
    c = cards["Electrolyze"]
    scry_id = c.card.identifiers["scryfallId"]
    img_url = (
        f"https://api.scryfall.com/cards/{scry_id}"
        f"?format=image&version=large"
    )
    with aioresponses() as mocked:
        mocked.get(url=img_url, status=400)
        with pytest.raises(ClientResponseError):
            await c.get_image(size="large")
