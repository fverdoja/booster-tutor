from typing import Sequence

import pytest
from boostertutor.models.mtg_pack import MtgCard


@pytest.mark.parametrize(
    ["card", "expected"],
    [
        ("Ghostly Prison", ["W"]),
        ("Clever Impersonator", ["U"]),
        ("Grim Haruspex", ["B"]),
        ("Desperate Ravings", ["R"]),
        ("Farseek", ["G"]),
        ("Scaretiller", []),
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
        ("Scaretiller", {"name": "Scaretiller", "count": 1}),
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
        ("Scaretiller", "1 Scaretiller (C19) 57"),
        ("Bojuka Bog", "1 Bojuka Bog (C19) 232"),
        ("Growing Ranks", "1 Growing Ranks (C19) 193"),
        ("Electrolyze", "1 Electrolyze (STA) 123"),
    ],
)
def test_arena(cards: dict[str, MtgCard], card: str, expected: str):
    assert cards[card].arena_format() == expected


def test_sort_key(cards: dict[str, MtgCard]):
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
        "Scaretiller",
        "Electrolyze",
        "Bojuka Bog",
    ]
