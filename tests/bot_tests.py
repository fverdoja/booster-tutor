from boostertutor.generator import MtgPackGenerator


def test_generator():
    generator = MtgPackGenerator()
    p = generator.get_pack("m21")
    assert len(p.cards) == 15 