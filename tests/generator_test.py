from collections import Counter

import pytest


def test_pack(generator):
    p = generator.get_pack("m21")
    assert len(p.cards) == 15
    assert p.is_balanced(rebalance=False)

    with pytest.raises(AssertionError):
        p = generator.get_pack("non existing set")

    p_list = generator.get_pack("znr", n=6)
    assert len(p_list) == 6
    assert all([pack.set.code == "ZNR" for pack in p_list])


def test_random_pack(generator):
    set_list = ["MB1", "APC", "MIR", "AKR"]
    p_list = generator.get_random_pack(sets=set_list, n=4)
    assert len(p_list) == 4
    assert set(set_list) == set([pack.set.code for pack in p_list])

    with pytest.raises(AssertionError):
        p_list = generator.get_random_pack(sets=set_list, n=5)

    p_list = generator.get_random_pack(sets=set_list, n=5, replace=True)
    assert len(p_list) == 5
    count_sets = Counter([pack.set.code for pack in p_list])
    assert any([c > 1 for c in count_sets.values()])


def test_jumpstart(generator):
    p = generator.get_random_jmp_deck()
    assert len(p.cards) == 20

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
