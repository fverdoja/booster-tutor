#!/usr/bin/env python

class MtgPack:
    def __init__(self, cards, set=None, name=None):
        self.cards = cards
        if set:
            self.set = set
        else:
            self.set = cards[0].card.set
        if name:
            self.name = name
        else:
            self.name = self.set.name

    def is_balanced(self):
        common_colors = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
        uncommon_colors = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
        found_common_creature = False
        for card in self.cards:
            if not card.foil and card.card.rarity == "common" \
                    and len(card.card.colors) == 1:
                common_colors[card.card.colors[0]] += 1
            if not card.foil and card.card.rarity == "uncommon" \
                    and len(card.card.colors) == 1:
                uncommon_colors[card.card.colors[0]] += 1
            if not card.foil and card.card.rarity == "common" \
                    and "Creature" in card.card.types:
                found_common_creature = True

        # A pack must never have more than 4 commons of the same color
        if any([c > 4 for c in common_colors.values()]):
            print(f"Discarded pack: commons {common_colors}")
            return False
        # A pack must have at least 1 common card of each color
        if not all(common_colors.values()):
            print(f"Discarded pack: commons {common_colors}")
            return False
        # A pack must have at least 1 common creature
        if not found_common_creature:
            print("Discarded pack: no common creature")
            return False
        # A pack must never have more than 2 uncommons of the same color
        if any([c > 2 for c in uncommon_colors.values()]):
            print(f"Discarded pack: uncommons {uncommon_colors}")
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
