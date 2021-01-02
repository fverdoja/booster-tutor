#!/usr/bin/env python

from mtg_pack_generator import MtgPackGenerator

if __name__ == "__main__":
    generator = MtgPackGenerator("mtg_pack_generator/data/AllPrintings.json")
    historic_sets = ["klr", "akr", "xln", "rix", "dom", "m19", "grn", "rna",
                     "war", "m20", "eld", "thb", "iko", "m21", "znr"]
    standard_sets = ["eld", "thb", "iko", "m21", "znr"]

    for i in range(6):
        p = generator.get_random_pack(historic_sets)
        print(p.get_arena_format())
