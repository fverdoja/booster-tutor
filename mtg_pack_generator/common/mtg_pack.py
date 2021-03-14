#!/usr/bin/env python

from random import choice


class MtgPack:
    def __init__(self, content, set=None, name=None):
        self.content = content
        if set:
            self.set = set
        else:
            self.set = self.cards[0].card.set
        if name:
            self.name = name
        else:
            self.name = self.set.name

    @property
    def cards(self):
        cards = []
        for slot in self.content.values():
            for card in slot["cards"]:
                cards.append(card)
        cards.sort(key=lambda x: x.pack_sort_key())
        return cards

    def is_balanced(self, rebalance=False):
        # Pack must never have duplicates (foil excluded)
        if self.has_duplicates():
            print("Discarded pack: duplicates")
            print(self.to_str())
            return False

        for slot_name, slot in self.content.items():
            card_names = [c.card.name for c in slot["cards"]]

            if slot["balance"]:  # commons
                # Pack must have at least 1 common card of each color
                if not self.balance_commons(slot_name, rebalance=rebalance):
                    print("Discarded pack: 1 color commons")
                    print(card_names)
                    return False

                # Pack must never have more than 4 commons of the same color
                if self.max_cards_per_color(slot_name) > 4:
                    print("Discarded pack: 5+ same color commons")
                    print(card_names)
                    return False

                # Pack must have at least 1 common creature
                if not self.contains_creature(slot_name):
                    print("Discarded pack: no common creature")
                    print(card_names)
                    return False
            elif not slot["cards"][0].foil \
                    and slot["cards"][0].card.rarity == "uncommon":
                # Pack must never have more than 2 uncommons of the same color
                if self.max_cards_per_color(slot_name) > 2:
                    print("Discarded pack: 3+ same color uncommons")
                    print(card_names)
                    return False
        return True

    def has_duplicates(self):
        cards_names = [c.card.name for c in self.cards if not c.foil]
        return len(cards_names) != len(set(cards_names))

    def balance_commons(self, slot_name, rebalance=False):
        slot = self.content[slot_name]
        assert(not rebalance or "backups" in slot)

        common_colors = {"W": [], "U": [], "B": [], "R": [], "G": [], "C": []}
        for card in slot["cards"]:
            if len(card.card.colors) == 1:
                common_colors[card.card.colors[0]].append(card)
            elif len(card.card.colors) == 0:
                common_colors["C"].append(card)
        common_counts = {k: len(v) for (k, v) in common_colors.items()}

        missing = sum([v == 0 for v in list(common_counts.values())[:5]])
        if missing:
            if rebalance:
                rebalanced = True
                print(f"Rebalancing: commons {common_counts}")
                backup_colors = {"W": [], "U": [], "B": [],
                                 "R": [], "G": [], "C": []}
                for card in slot["backups"]:
                    assert(not card.foil and card.card.rarity == "common")
                    if len(card.card.colors) == 1:
                        backup_colors[card.card.colors[0]].append(card)
                    elif len(card.card.colors) == 0:
                        backup_colors["C"].append(card)
                backup_counts = {k: len(v) for (k, v) in backup_colors.items()}
                for color in common_colors:
                    if color != "C" and not common_counts[color]:
                        if backup_counts[color]:
                            max_count = max(common_counts.items(),
                                            key=lambda x: x[1])[1]
                            swap_colors = [k for k in common_counts
                                           if common_counts[k] == max_count]
                            if len(swap_colors) > 1 and "C" in swap_colors:
                                swap_colors.remove("C")
                            if max_count > 1:
                                swap_color = choice(swap_colors)
                                swap = common_colors[swap_color].pop()
                                bkp = backup_colors[color].pop()
                                common_counts[swap_color] -= 1
                                common_counts[color] += 1
                                backup_counts[color] -= 1
                                common_colors[color].append(bkp)
                                slot["cards"] = [bkp if c is swap else c
                                                 for c in slot["cards"]]
                                slot["backups"] = [c for c in slot["backups"]
                                                   if c is not bkp]
                                print(f"Rebalancing: {color} -> {swap_color}")
                            else:
                                print(f"Rebalancing: {color} failed (no swap)")
                                rebalanced = False
                        else:
                            print(f"Rebalancing: {color} failed (no backup)")
                            rebalanced = False
            else:
                rebalanced = False

            if rebalanced:
                print(f"Rebalanced: commons {common_counts}")
            else:
                return False
        return True

    def max_cards_per_color(self, slot_name=None):
        if slot_name is not None:
            cards = self.content[slot_name]["cards"]
        else:
            cards = self.cards

        colors = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
        for card in cards:
            if len(card.card.colors) == 1:
                colors[card.card.colors[0]] += 1
        return max(colors.values())

    def contains_creature(self, slot_name=None):
        if slot_name is not None:
            cards = self.content[slot_name]["cards"]
        else:
            cards = self.cards

        for card in cards:
            if "Creature" in card.card.types:
                return True
        return False

    async def get_images(self, size="normal", foil=None):
        img = [await c.get_image(size, foil) for c in self.cards]
        return img

    def get_arena_format(self):
        ret = ""
        for card in self.cards:
            ret += f"{card.get_arena_format()}\n"

        return ret.strip()

    def to_str(self):
        ret = ""
        for card in self.cards:
            ret += f"{card.to_str()}\n"

        return ret.strip()
