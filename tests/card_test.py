from contextlib import nullcontext as not_raise
from io import BytesIO
from typing import ContextManager, Literal, Optional, Sequence

import imageio.v3 as iio
import numpy as np
import pytest
from aiohttp import ClientResponseError
from aioresponses import aioresponses

from boostertutor.models.mtg_card import CardImageSize, MtgCard


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
def test_colors(
    cards: dict[str, MtgCard], card: str, expected: Sequence[str]
) -> None:
    assert cards[card].mana() == expected


@pytest.mark.parametrize(
    ["card", "expected"],
    [
        (
            "Ghostly Prison",
            {"name": "Ghostly Prison", "set": "C19", "count": 1},
        ),
        (
            "Clever Impersonator",
            {"name": "Clever Impersonator", "set": "C19", "count": 1},
        ),
        ("Grim Haruspex", {"name": "Grim Haruspex", "set": "C19", "count": 1}),
        (
            "Desperate Ravings",
            {"name": "Desperate Ravings", "set": "C19", "count": 1},
        ),
        ("Farseek", {"name": "Farseek", "set": "C19", "count": 1}),
        (
            "Mysterious Egg",
            {"name": "Mysterious Egg", "set": "IKO", "count": 1},
        ),
        ("Bojuka Bog", {"name": "Bojuka Bog", "set": "C19", "count": 1}),
        ("Growing Ranks", {"name": "Growing Ranks", "set": "C19", "count": 1}),
        ("Electrolyze", {"name": "Electrolyze", "set": "STA", "count": 1}),
        (
            "Urza, Lord Protector",
            {"name": "Urza, Lord Protector", "set": "BRO", "count": 1},
        ),
        (
            "The Mightstone and Weakstone",
            {"name": "The Mightstone and Weakstone", "set": "BRO", "count": 1},
        ),
    ],
)
def test_json(cards: dict[str, MtgCard], card: str, expected: dict) -> None:
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
        ("Urza, Lord Protector", "1 Urza, Lord Protector (BRO) 225"),
        (
            "The Mightstone and Weakstone",
            "1 The Mightstone and Weakstone (BRO) 238a",
        ),
    ],
)
def test_arena(cards: dict[str, MtgCard], card: str, expected: str) -> None:
    assert cards[card].arena_format() == expected


def test_arena_promo(cards: dict[str, MtgCard]) -> None:
    promo = cards["Mysterious Egg"]
    assert promo.meta.number == "385"  # check that it's the promo version
    assert promo.arena_format() == "1 Mysterious Egg (IKO) 3"


def test_pack_sort_key(cards: dict[str, MtgCard]) -> None:
    card_list = list(cards.values())
    card_list.sort(key=lambda x: x.pack_sort_key())
    names = [card.meta.name for card in card_list]
    assert names == [
        "Clever Impersonator",
        "Urza, Lord Protector // Urza, Planeswalker",
        "Grim Haruspex",
        "Growing Ranks",
        "The Mightstone and Weakstone // Urza, Planeswalker",
        "Ghostly Prison",
        "Desperate Ravings",
        "Farseek",
        "Mysterious Egg",
        "Electrolyze",
        "Bojuka Bog",
    ]


@pytest.mark.parametrize(
    ["card", "currency", "is_none", "rate_none", "expected", "expected_raise"],
    [
        ("Ghostly Prison", "eur", False, False, 1.0, not_raise()),  # eur
        ("Electrolyze", "eur", False, False, 3.0, not_raise()),  # eur_foil
        ("Ghostly Prison", "usd", False, False, 2.6, not_raise()),  # usd
        ("Electrolyze", "usd", False, False, 5.2, not_raise()),  # usd_foil
        ("Ghostly Prison", "eur", True, False, 2.0, not_raise()),  # eur conv
        ("Electrolyze", "eur", True, False, 4.0, not_raise()),  # eur_foil conv
        ("Ghostly Prison", "usd", True, False, 1.3, not_raise()),  # usd conv
        ("Electrolyze", "usd", True, False, 3.9, not_raise()),  # usd_foil conv
        ("Ghostly Prison", "eur", True, True, None, not_raise()),  # no rate
        ("Electrolyze", "wrong", False, False, 1.0, pytest.raises(ValueError)),
    ],
)
async def test_prices(
    cards: dict[str, MtgCard],
    card: str,
    currency: Literal["eur", "usd"],
    is_none: bool,
    rate_none: bool,
    expected: float,
    expected_raise: ContextManager,
) -> None:
    c = cards[card]
    prices: dict[str, Optional[str]] = {
        "eur": "1.0",
        "eur_foil": "3.0",
        "usd": "2.6",
        "usd_foil": "5.2",
    }
    if is_none:
        prices[currency] = None
        prices[currency + "_foil"] = None
    rate = None if rate_none else 1.3
    scry_id = c.meta.identifiers.scryfall_id
    card_url = f"https://api.scryfall.com/cards/{scry_id}"
    with aioresponses() as mocked:
        mocked.get(url=card_url, status=200, payload={"prices": prices})
        with expected_raise:
            price = await c.get_price(currency=currency, eur_usd_rate=rate)
            assert price == pytest.approx(expected)


@pytest.mark.parametrize(
    ["size", "foil", "expected_shape", "expected_raise"],
    [
        ("large", None, (936, 672, 3), not_raise()),
        ("normal", False, (680, 488, 3), not_raise()),
        ("small", True, (204, 146, 3), not_raise()),
        ("wrong_size", None, (1, 1, 3), pytest.raises(ValueError)),
    ],
)
async def test_image(
    cards: dict[str, MtgCard],
    size: CardImageSize,
    foil: Optional[bool],
    expected_shape: tuple[int, int, int],
    expected_raise: ContextManager,
) -> None:
    c = cards["Electrolyze"]  # foil card, produces a foil image by default
    scry_id = c.meta.identifiers.scryfall_id
    img_url = (
        f"https://api.scryfall.com/cards/{scry_id}"
        f"?format=image&version={size}"
    )
    expected_img = np.zeros(expected_shape, dtype="uint8")
    mock_img_file = BytesIO()
    iio.imwrite(mock_img_file, expected_img, extension=".jpg")
    with aioresponses() as mocked:
        mocked.get(url=img_url, status=200, body=mock_img_file.getvalue())
        with expected_raise:
            img = await c.get_image(size, foil)

            # if None or foil, the image should have been applied a foil
            # effect, so it should not match the original image
            expected_equal = not foil if foil is not None else False

            assert img.shape == expected_shape
            assert np.array_equal(img, expected_img) == expected_equal


async def test_image_400(cards: dict[str, MtgCard]) -> None:
    c = cards["Electrolyze"]
    scry_id = c.meta.identifiers.scryfall_id
    img_url = (
        f"https://api.scryfall.com/cards/{scry_id}"
        f"?format=image&version=large"
    )
    with aioresponses() as mocked:
        mocked.get(url=img_url, status=400)
        with pytest.raises(ClientResponseError):
            await c.get_image(size="large")
