#!/usr/bin/env python

from mtg_pack_generator import MtgPackGenerator


def main():
    generator = MtgPackGenerator("mtg_pack_generator/data/AllPrintings.json")

    for i in range(6):
        p = generator.get_pack("m21")
        print(p.get_arena_format())


if __name__ == "__main__":
    main()
