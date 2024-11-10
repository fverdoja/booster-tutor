import logging
import re
from collections import Counter
from typing import Sequence
from unittest import mock

import pytest
from aioresponses import aioresponses

from boostertutor.generator import MtgPackGenerator
from boostertutor.models.mtgjson_sql import (
    BoosterMeta,
    BoosterType,
    SetMeta,
    SheetMeta,
)


@pytest.mark.parametrize(
    ["card_ids", "expected_num_warnings"],
    [(["mocked_id_0", "mocked_id_1"], 0), (["mocked_id_2", "mocked_id_3"], 2)],
)
def test_booster_data_validation(
    generator: MtgPackGenerator,
    card_ids: Sequence[str],
    expected_num_warnings: int,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(generator, "sets_with_boosters", ["mocked_set"])
    monkeypatch.setattr(
        generator.data,
        "cards_by_id",
        {
            "mocked_id_0": "mocked_card_0",
            "mocked_id_1": "mocked_card_1",
        },
    )
    mocked_sheet: SheetMeta = mock.MagicMock(
        name="mocked_sheet",
        cards=[mock.MagicMock(_uuid=card_id) for card_id in card_ids],
    )
    mocked_booster: BoosterMeta = mock.MagicMock(sheets=[mocked_sheet])
    mocked_set: SetMeta = mock.MagicMock(
        boosters={"mocked_booster": mocked_booster}
    )
    monkeypatch.setitem(generator.data.sets, "mocked_set", mocked_set)

    with caplog.at_level(logging.WARNING):
        num_warnings = generator.validate_booster_data()
        assert num_warnings == expected_num_warnings
        if expected_num_warnings:
            assert "Found non-existent card id in a booster" in caplog.text
            assert "Generating boosters with non-existent card" in caplog.text
        else:
            assert caplog.text == ""


def test_pack(generator: MtgPackGenerator) -> None:
    p = generator.get_pack("m21")
    assert len(p.cards) == 15
    assert p.is_balanced(rebalance=False)


def test_collector_pack(generator: MtgPackGenerator) -> None:
    p = generator.get_pack("m21", booster_type=BoosterType.COLLECTOR)
    assert len(p.cards) == 15


def test_pack_raises(generator: MtgPackGenerator) -> None:
    with pytest.raises(AssertionError):
        generator.get_pack("non existing set")


def test_pack_collector_raises(generator: MtgPackGenerator) -> None:
    with pytest.raises(ValueError):
        generator.get_pack("inv", booster_type=BoosterType.COLLECTOR)


def test_pack_list(generator: MtgPackGenerator) -> None:
    p_list = generator.get_packs("znr", n=6)
    assert len(p_list) == 6
    assert all([pack.set.code == "ZNR" for pack in p_list])


def test_all_packs(generator: MtgPackGenerator) -> None:
    p_list = [generator.get_pack(set) for set in generator.sets_with_boosters]
    assert all(
        [
            not p.can_be_balanced() or p.is_balanced(rebalance=False)
            for p in p_list
        ]
    )


def test_random_pack(generator: MtgPackGenerator) -> None:
    p = generator.get_random_packs()[0]
    assert p.set.code in generator.sets_with_boosters


def test_random_packs_from_set_list(
    generator: MtgPackGenerator, four_set_list: list[str]
) -> None:
    p_list = generator.get_random_packs(sets=four_set_list, n=4)
    assert len(p_list) == 4
    assert set(four_set_list) == set([pack.set.code for pack in p_list])


def test_random_packs_from_set_list_raises(
    generator: MtgPackGenerator, four_set_list: list[str]
) -> None:
    with pytest.raises(AssertionError):
        generator.get_random_packs(sets=four_set_list, n=5)


def test_random_packs_from_set_list_with_replacement(
    generator: MtgPackGenerator, four_set_list: list[str]
) -> None:
    p_list = generator.get_random_packs(sets=four_set_list, n=5, replace=True)
    assert len(p_list) == 5
    count_sets = Counter([pack.set.code for pack in p_list])
    assert any([c > 1 for c in count_sets.values()])


def test_has_jumpstart(generator: MtgPackGenerator) -> None:
    assert len(generator.data.sets["JMP"].boosters) == 1
    for deck in (
        generator.data.sets["JMP"].boosters[BoosterType.JUMPSTART].variations
    ):
        assert deck.weight == 1
        assert len(deck.content) == 1
        assert sum([c.weight for c in deck.content[0].sheet.cards]) == 20
    assert len(generator.data.sets["J22"].boosters) == 1
    for deck in (
        generator.data.sets["J22"].boosters[BoosterType.JUMPSTART].variations
    ):
        assert deck.weight == 1
        assert len(deck.content) == 1
        assert sum([c.weight for c in deck.content[0].sheet.cards]) == 20
    assert len(generator.data.sets["J25"].boosters) == 1
    for deck in (
        generator.data.sets["J25"].boosters[BoosterType.JUMPSTART].variations
    ):
        assert deck.weight == 1
        assert len(deck.content) == 1
        assert sum([c.weight for c in deck.content[0].sheet.cards]) == 20


def test_jumpstart(generator: MtgPackGenerator) -> None:
    p = generator.get_random_decks("JMP")[0]
    assert len(p.cards) == 20


def test_jumpstart_list(generator: MtgPackGenerator) -> None:
    p_list = generator.get_random_decks("J22", n=2)
    assert len(p_list) == 2
    assert all([pack.set.code == "J22" for pack in p_list])


def test_arena_jumpstart(generator: MtgPackGenerator) -> None:
    all_jmp_decks = generator.get_random_arena_jmp_decks(n=121, replace=False)
    all_cards = [card for deck in all_jmp_decks for card in deck.cards]
    assert all([c.meta.name != "Rhystic Study" for c in all_cards])
    assert all([c.meta.set_code != "AJMP" for c in all_cards])


def test_cube_pack(generator: MtgPackGenerator, cube: dict) -> None:
    p = generator.get_cube_pack(cube)
    assert len(p.cards) == 15
    assert p.name == "Test Cube"
    assert sum([card.foil for card in p.cards]) == 2


@pytest.mark.parametrize(
    ["draft_format", "expected_len", "expected_dups"],
    [
        (
            {
                "packs": [
                    {
                        "slots": [
                            't:"Foil"',
                            't:"Etched"',
                            't:"Non-foil"',
                            't:"Non-foil"',
                            't:"Double"',
                        ]
                    }
                ],
                "multiples": False,
            },
            5,
            False,
        ),
        (
            {
                "packs": [
                    {
                        "slots": [
                            "tag:Foil",
                            "tag:Etched",
                            "tag:Non-foil",
                            "tag:Non-foil",
                            "tag:Double",
                            "tag:Double",
                        ]
                    }
                ],
                "multiples": True,
            },
            6,
            True,
        ),
        (
            {
                "packs": [{"slots": ["tag:Foil", "tag:Etched"]}],
                "multiples": False,
            },
            2,
            False,
        ),
        (
            {
                "packs": [{"slots": ["rarity:Rare"]}],
                "multiples": False,
            },
            15,
            False,
        ),
    ],
)
def test_cube_pack_custom(
    generator: MtgPackGenerator,
    cube: dict,
    draft_format: dict,
    expected_len: int,
    expected_dups: bool,
) -> None:
    cube["formats"] = [draft_format]
    p = generator.get_cube_pack(cube)
    copy_count = Counter([c.meta.name for c in p.cards])
    assert len(p.cards) == expected_len
    assert sum([card.foil for card in p.cards]) == 2
    assert (copy_count["Dega Disciple"] == 2) == expected_dups


def test_cube_pack_list(generator: MtgPackGenerator, cube: dict) -> None:
    p_list = generator.get_cube_packs(cube, n=6)
    assert len(p_list) == 6
    assert all([pack.name == "Test Cube" for pack in p_list])


async def test_pack_ev(generator: MtgPackGenerator) -> None:
    pattern = re.compile(r"^https://api\.scryfall\.com/cards.*$")
    prices = {"prices": {"eur": "1.0", "eur_foil": "1.0"}}
    with aioresponses() as mocked:
        mocked.get(url=pattern, status=200, payload=prices, repeat=True)
        ev = await generator.get_pack_ev(set="mh2", currency="eur")
    assert ev == pytest.approx(15)


async def test_pack_ev_bulk(generator: MtgPackGenerator) -> None:
    pattern = re.compile(r"^https://api\.scryfall\.com/cards.*$")
    prices = {"prices": {"eur": "1.0", "eur_foil": "3.0"}}
    with aioresponses() as mocked:
        mocked.get(url=pattern, status=200, payload=prices, repeat=True)
        ev = await generator.get_pack_ev(
            set="mh2", currency="eur", bulk_threshold=1.5
        )
    assert ev == pytest.approx(1)
