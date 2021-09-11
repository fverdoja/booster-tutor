from collections import Counter


def test_pack_generation(generator):
    p = generator.get_pack("m21")
    assert len(p.cards) == 15

    p_list = generator.get_pack("znr", n=6)
    assert len(p_list) == 6
    assert all([pack.set.code == "ZNR" for pack in p_list])


def test_random_pack_generation(generator):
    set_list = ["MB1", "APC", "MIR", "AKR"]
    p_list = generator.get_random_pack(sets=set_list, n=4)
    assert len(p_list) == 4
    assert set(set_list) == set([pack.set.code for pack in p_list])

    p_list = generator.get_random_pack(sets=set_list, n=6, replace=True)
    assert len(p_list) == 6
    count_sets = Counter([pack.set.code for pack in p_list])
    assert any([c > 1 for c in count_sets.values()])


def test_rebalancing(generator):
    p = generator.get_pack("DOM")
    assert len(p.cards) == 15
    assert p.is_balanced(rebalance=False)
