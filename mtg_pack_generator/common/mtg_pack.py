#!/usr/bin/env python

from random import choice


class MtgPack:
    def __init__(self, cards, backup=None, set=None, name=None):
        self.cards = cards
        self.backup_cards = backup
        if set:
            self.set = set
        else:
            self.set = cards[0].card.set
        if name:
            self.name = name
        else:
            self.name = self.set.name

    def sort_by_rarity(self, reverse=False):
        self.cards.sort(key=lambda x: x.pack_sort_key(), reverse=reverse)

    def is_balanced(self, rebalance=False):
        common_colors = {"W": [], "U": [], "B": [], "R": [], "G": [], "C": []}
        uncommon_colors = {"W": [], "U": [], "B": [], "R": [], "G": []}
        found_common_creature = False
        for card in self.cards:
            if not card.foil and card.card.rarity == "common":
                if len(card.card.colors) == 1:
                    common_colors[card.card.colors[0]].append(card)
                elif len(card.card.colors) == 0:
                    common_colors["C"].append(card)
            if not card.foil and card.card.rarity == "uncommon" \
                    and len(card.card.colors) == 1:
                uncommon_colors[card.card.colors[0]].append(card)
            if not card.foil and card.card.rarity == "common" \
                    and "Creature" in card.card.types:
                found_common_creature = True

        common_counts = {k: len(v) for (k, v) in common_colors.items()}
        uncommon_counts = {k: len(v) for (k, v) in uncommon_colors.items()}

        # A pack must have at least 1 common card of each color, with each
        # colorless card counting for one of the missing colors
        missing = sum([v == 0 for v in list(common_counts.values())[:5]])
        if missing:
            if rebalance:
                rebalanced = True
                print(f"Rebalancing: commons {common_counts}")
                backup_colors = {"W": [], "U": [], "B": [],
                                 "R": [], "G": [], "C": []}
                for card in self.backup_cards:
                    assert(not card.foil and card.card.rarity == "common")
                    if len(card.card.colors) == 1:
                        backup_colors[card.card.colors[0]].append(card)
                    elif len(card.card.colors) == 0:
                        backup_colors["C"].append(card)
                backup_counts = {k: len(v) for (k, v) in backup_colors.items()}
                for color in common_colors:
                    if not common_counts[color]:
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
                                backup = backup_colors[color].pop()
                                common_counts[swap_color] -= 1
                                common_counts[color] += 1
                                backup_counts[color] -= 1
                                common_colors[color].append(backup)
                                self.cards = [backup if c is swap else c
                                              for c in self.cards]
                                self.backup_cards = [c for c
                                                     in self.backup_cards
                                                     if c is not backup]
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
                r = False  # random() < .3
                if r and missing == 1 and common_counts["C"] > 1:
                    print(f"Warning: commons {common_counts}")
                else:
                    print(f"Discarded pack: commons {common_counts}")
                    return False
        # A pack must never have more than 4 commons of the same color
        if any([c > 4 for c in common_counts.values()]):
            print(f"Discarded pack: 5 commons {common_counts}")
            return False
        # A pack must have at least 1 common creature
        if not found_common_creature:
            print("Discarded pack: no common creature")
            return False
        # A pack must never have more than 2 uncommons of the same color
        if any([c > 2 for c in uncommon_counts.values()]):
            print(f"Discarded pack: uncommons {uncommon_counts}")
            return False
        # A pack must never have duplicates (foil excluded)
        cards_names = [c.card.name for c in self.cards if not c.foil]
        if len(cards_names) != len(set(cards_names)):
            print("Discarded pack: duplicates")
            return False

        return True

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
