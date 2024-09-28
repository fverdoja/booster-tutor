import pytest

from boostertutor.models.mtg_card import MtgCard
from boostertutor.models.mtg_pack import MtgPack
from boostertutor.models.mtgjson_sql import BoosterType


def test_duplicates(unbalanced_pack: MtgPack) -> None:
    assert not unbalanced_pack.has_duplicates()
    card = unbalanced_pack.content["nonlandCommon"]["cards"][0]
    unbalanced_pack.content["nonlandCommon"]["cards"].append(card)
    assert unbalanced_pack.has_duplicates()


def test_duplicates_in_foil(unbalanced_pack: MtgPack) -> None:
    card = unbalanced_pack.content["nonlandCommon"]["cards"][0]
    card.foil = True
    unbalanced_pack.content["foil"] = {"cards": [card], "balance": False}
    assert not unbalanced_pack.has_duplicates()


def test_max_allowed_missing_colors(
    unbalanced_pack: MtgPack, unbalanced_play_pack: MtgPack
) -> None:
    assert unbalanced_pack.max_allowed_missing_colors() == 0
    assert unbalanced_play_pack.max_allowed_missing_colors() == 1
    play_arena_pack = MtgPack(
        content=unbalanced_play_pack.content, type=BoosterType.PLAY_ARENA
    )
    assert play_arena_pack.max_allowed_missing_colors() == 1


@pytest.mark.parametrize("count_hybrids", [True, False])
def test_count_card_colors(
    cards: dict[str, MtgCard], count_hybrids: bool
) -> None:
    card_list = list(cards.values())
    pack = MtgPack({"slot": {"cards": card_list}})
    colors, counts = pack.count_cards_colors(
        card_list, count_hybrids=count_hybrids
    )
    assert counts == {
        "W": 2 if count_hybrids else 1,
        "U": 1,
        "B": 1,
        "R": 1,
        "G": 2 if count_hybrids else 1,
        "C": 3,
    }


def test_arena(cards: dict[str, MtgCard]) -> None:
    card_list = [
        cards["Electrolyze"],
        cards["The Mightstone and Weakstone"],
        cards["Mysterious Egg"],
    ]
    pack = MtgPack({"slot": {"cards": card_list}})
    assert pack.arena_format() == (
        "1 The Mightstone and Weakstone (BRO) 238a\n"
        "1 Mysterious Egg (IKO) 3\n"
        "1 Electrolyze (STA) 123"
    )


def test_json(cards: dict[str, MtgCard]) -> None:
    card_list = [
        cards["Electrolyze"],
        cards["The Mightstone and Weakstone"],
        cards["Mysterious Egg"],
    ]
    pack = MtgPack({"slot": {"cards": card_list}})
    assert pack.json() == [
        {"name": "The Mightstone and Weakstone", "set": "BRO", "count": 1},
        {"name": "Mysterious Egg", "set": "IKO", "count": 1},
        {"name": "Electrolyze", "set": "STA", "count": 1},
    ]


def test_balancing(unbalanced_pack: MtgPack) -> None:
    assert not unbalanced_pack.is_balanced()
    unbalanced_pack.is_balanced(rebalance=True)
    assert unbalanced_pack.is_balanced()

    cards = [c.meta.name for c in unbalanced_pack.cards]
    assert "Griffin Protector" not in cards
    assert "Fortress Crab" in cards


def test_play_balancing(unbalanced_play_pack: MtgPack) -> None:
    assert not unbalanced_play_pack.is_balanced()
    unbalanced_play_pack.is_balanced(rebalance=True)
    assert unbalanced_play_pack.is_balanced()

    cards = [c.meta.name for c in unbalanced_play_pack.cards]
    assert "Griffin Protector" not in cards
    assert "Fortress Crab" in cards


async def test_image(
    unbalanced_pack: MtgPack, mocked_aioresponses: None
) -> None:
    img_list = await unbalanced_pack.get_images()

    assert len(img_list) == len(unbalanced_pack.cards)
    assert all([i.shape == (10, 10, 3) for i in img_list])
