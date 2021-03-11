#!/usr/bin/env python

from numpy.random import choice

from .common.mtg_card import MtgCard
from .common.mtg_pack import MtgPack
from .common.mtgjson import CardDb


class MtgPackGenerator:
    def __init__(self, path_to_mtgjson="data/AllPrintings.json",
                 max_balancing_iterations=100):
        self.max_balancing_iterations = max_balancing_iterations
        self.data = CardDb.from_file(path_to_mtgjson)
        self.fix_iko()
        self.sets_with_boosters = []
        for s in self.data.sets:
            if hasattr(self.data.sets[s], "booster"):
                self.sets_with_boosters.append(s)

    def get_pack(self, set, n=1, balance=True):
        if n == 1:
            print(f"Generating {set.upper()} pack...")
            iterations = self.max_balancing_iterations if balance else 1
            return self.get_pack_internal(set, iterations)
        else:
            return [self.get_pack(set, balance=balance) for i in range(n)]

    def get_pack_internal(self, set, iterations):
        assert(set.upper() in self.data.sets)

        booster = self.data.sets[set.upper()].booster
        if "default" in booster:
            booster_meta = booster["default"]
        elif "arena" in booster:
            booster_meta = booster["arena"]
        else:
            booster_type = next(iter(booster))
            booster_meta = booster[booster_type]

        boosters_p = [x["weight"] / booster_meta["boostersTotalWeight"]
                      for x in booster_meta["boosters"]]

        booster = booster_meta["boosters"][choice(
            len(booster_meta["boosters"]), p=boosters_p)]["contents"]

        pack_content = []
        pack_backup = []

        balance = False
        for sheet_name, k in booster.items():
            sheet_meta = booster_meta["sheets"][sheet_name]
            if "balanceColors" in sheet_meta.keys():
                balance = balance or sheet_meta["balanceColors"]
                num_of_backups = 20
            else:
                num_of_backups = 0

            cards = list(sheet_meta["cards"].keys())
            cards_p = [x / sheet_meta["totalWeight"]
                       for x in sheet_meta["cards"].values()]

            picks = choice(cards, size=k + num_of_backups,
                           replace=False, p=cards_p)

            pick_i = 0
            for card_id in picks:
                if pick_i < k:
                    pack_content.append(MtgCard(
                        self.data.cards_by_id[card_id], sheet_meta["foil"]))
                else:
                    pack_backup.append(MtgCard(
                        self.data.cards_by_id[card_id], sheet_meta["foil"]))
                pick_i += 1
            pack_content = self.replace_promos(pack_content)
            pack_backup = self.replace_promos(pack_backup)

        if "name" in booster_meta:
            pack_name = booster_meta["name"]
        else:
            pack_name = None
        if not len(pack_backup):
            pack_backup = None
        pack = MtgPack(pack_content, backup=pack_backup, name=pack_name)

        if not balance:
            print("Pack should not be balanced, skipping.")
            iterations = 1

        if iterations <= 1 or pack.is_balanced(rebalance=True):
            print(f"{set.upper()} pack generated, iterations needed: "
                  f"{str(self.max_balancing_iterations - iterations + 1)}")
            return pack
        else:
            return self.get_pack_internal(set, iterations-1)

    def get_random_pack(self, sets=None, n=1, replace=False, balance=True):
        if sets is None:
            sets = self.sets_with_boosters

        assert(replace or n <= len(sets))

        boosters = choice(sets, size=n, replace=replace)
        if n == 1:
            return self.get_pack(set=boosters[0], balance=balance)
        else:
            return [self.get_pack(set=b, balance=balance) for b in boosters]

    def fix_iko(self):
        iko = self.data.sets["IKO"]
        iko.booster["default"]["sheets"]["common"]["balanceColors"] = True

    def replace_promos(self, cards):
        res = []
        for c in cards:
            if hasattr(c.card, "promoTypes"):
                base_id = c.card.variations[0]
                res.append(MtgCard(self.data.cards_by_id[base_id], c.foil))
                print(f"Replaced Promo {c.card.name}")
            else:
                res.append(c)
        return res
