from collections import Counter

import pytest


def test_pack(generator):
    p = generator.get_pack("m21")
    assert len(p.cards) == 15
    assert p.is_balanced(rebalance=False)


def test_pack_raises(generator):
    with pytest.raises(AssertionError):
        generator.get_pack("non existing set")


def test_pack_list(generator):
    p_list = generator.get_pack("znr", n=6)
    assert len(p_list) == 6
    assert all([pack.set.code == "ZNR" for pack in p_list])


def test_all_packs(generator):
    p_list = [generator.get_pack(set) for set in generator.sets_with_boosters]
    assert all(
        [
            not p.can_be_balanced() or p.is_balanced(rebalance=False)
            for p in p_list
        ]
    )


def test_random_pack(generator):
    p = generator.get_random_pack()
    assert p.set.code in generator.sets_with_boosters


def test_random_packs_from_set_list(generator, four_set_list):
    p_list = generator.get_random_pack(sets=four_set_list, n=4)
    assert len(p_list) == 4
    assert set(four_set_list) == set([pack.set.code for pack in p_list])


def test_random_packs_from_set_list_raises(generator, four_set_list):
    with pytest.raises(AssertionError):
        generator.get_random_pack(sets=four_set_list, n=5)


def test_random_packs_from_set_list_with_replacement(generator, four_set_list):
    p_list = generator.get_random_pack(sets=four_set_list, n=5, replace=True)
    assert len(p_list) == 5
    count_sets = Counter([pack.set.code for pack in p_list])
    assert any([c > 1 for c in count_sets.values()])


def test_jumpstart(generator):
    p = generator.get_random_jmp_deck()
    assert len(p.cards) == 20


def test_jumpstart_list(generator):
    p_list = generator.get_random_jmp_deck(n=2)
    assert len(p_list) == 2
    assert all([pack.set.code == "JMP" for pack in p_list])


def test_arena_jumpstart(generator):
    for d in generator.data.sets["JMP"].decks:
        for c in d["mainBoard"]:
            assert c.name != "Path to Exile"


def test_balancing(unbalanced_pack):
    assert not unbalanced_pack.is_balanced()
    unbalanced_pack.is_balanced(rebalance=True)
    assert unbalanced_pack.is_balanced()

    cards = [c.card.name for c in unbalanced_pack.cards]
    assert "Griffin Protector" not in cards
    assert "Fortress Crab" in cards
