import logging
from random import choice
from typing import Optional, Sequence

import numpy as np
from boostertutor.models.mtg_card import MtgCard
from boostertutor.models.mtgjson import SetProxy

logger = logging.getLogger(__name__)


class MtgPack:
    def __init__(
        self,
        content: dict,
        set: Optional[SetProxy] = None,
        name: Optional[str] = None,
    ):
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
    def cards(self) -> Sequence[MtgCard]:
        cards = [
            card for slot in self.content.values() for card in slot["cards"]
        ]
        cards.sort(key=lambda x: x.pack_sort_key())
        return cards

    def can_be_balanced(self) -> bool:
        return any([slot["balance"] for slot in self.content.values()])

    def is_balanced(self, rebalance: bool = False) -> bool:
        for slot_name, slot in self.content.items():
            card_names = [c.card.name for c in slot["cards"]]

            if slot["balance"]:  # commons
                # Pack must have at least 1 common card of each color
                if not self.balanced_commons(slot_name, rebalance=rebalance):
                    logger.warning(
                        f"Discarded pack: 1 color commons\n{card_names}"
                    )
                    return False

                # Pack must never have more than 4 commons of the same color
                if self.max_cards_per_color(slot_name) > 4:
                    logger.warning(
                        "Discarded pack: 5+ same color commons\n"
                        f"{card_names}"
                    )
                    return False

                # Pack must have at least 1 common creature
                if not self.contains_creature(slot_name):
                    logger.warning(
                        f"Discarded pack: no common creature\n{card_names}"
                    )
                    return False
            elif (
                not slot["cards"][0].foil
                and slot["cards"][0].card.rarity == "uncommon"
            ):
                # Pack must never have more than 2 uncommons of the same color
                if self.max_cards_per_color(slot_name) > 2:
                    logger.warning(
                        "Discarded pack: 3+ same color uncommons\n"
                        f"{card_names}"
                    )
                    return False

        # Pack must never have duplicates (foil excluded)
        if self.has_duplicates():
            logger.warning(f"Discarded pack: duplicates\n{self}")
            return False

        return True

    def has_duplicates(self) -> bool:
        cards_names = [c.card.name for c in self.cards if not c.foil]
        return len(cards_names) != len(set(cards_names))

    def count_cards_colors(
        self, card_list: Sequence[MtgCard], count_hybrids: bool = True
    ) -> tuple[dict[str, list[MtgCard]], dict[str, int]]:
        colors: dict[str, list[MtgCard]] = {
            "W": [],
            "U": [],
            "B": [],
            "R": [],
            "G": [],
            "C": [],
        }
        for card in card_list:
            if len(card.mana()) == 1:
                # hybrid cards go in two colors
                if count_hybrids:
                    for color in card.mana()[0]:
                        colors[color].append(card)
                # hybrid cards are considered multicolor and not counted
                else:
                    if len(card.mana()[0]) == 1:
                        colors[card.mana()[0]].append(card)
            elif len(card.mana()) == 0:
                colors["C"].append(card)
        counts = {k: len(v) for (k, v) in colors.items()}
        return (colors, counts)

    def balanced_commons(
        self, slot_name: str, rebalance: bool = False
    ) -> bool:
        slot = self.content[slot_name]
        assert not rebalance or "backups" in slot

        (_, common_counts) = self.count_cards_colors(slot["cards"])

        missing = sum([v == 0 for v in list(common_counts.values())[:5]])
        if missing:
            if rebalance:
                logger.debug(f"Rebalancing: commons {common_counts}")
                return self.rebalance_commons(slot)
            else:
                return False
        return True

    def rebalance_commons(self, slot: dict[str, Sequence[MtgCard]]) -> bool:
        (common_colors, common_counts) = self.count_cards_colors(slot["cards"])
        (bkp_colors, bkp_counts) = self.count_cards_colors(slot["backups"])

        missing_colors = [
            c for (c, v) in common_counts.items() if c != "C" and v == 0
        ]

        if missing_colors:
            color = missing_colors[0]
            if bkp_counts[color]:
                max_count = max(common_counts.items(), key=lambda x: x[1])[1]
                swap_colors = [
                    k for k in common_counts if common_counts[k] == max_count
                ]
                if len(swap_colors) > 1 and "C" in swap_colors:
                    swap_colors.remove("C")
                if max_count > 1:
                    swap_color = choice(swap_colors)
                    swap = common_colors[swap_color].pop()
                    bkp = bkp_colors[color].pop()

                    slot["cards"] = [
                        bkp if c is swap else c for c in slot["cards"]
                    ]
                    slot["backups"] = [
                        c for c in slot["backups"] if c is not bkp
                    ]
                    logger.debug(f"Rebalancing: {color} -> {swap_color}")
                    return self.rebalance_commons(slot)
                else:
                    logger.warning(f"Rebalancing: {color} failed (no swap)")
                    return False
            else:
                logger.warning(f"Rebalancing: {color} failed (no backup)")
                return False

        logger.debug(f"Rebalanced: commons {common_counts}")
        return True

    def max_cards_per_color(self, slot_name: Optional[str] = None) -> int:
        if slot_name is not None:
            cards = self.content[slot_name]["cards"]
        else:
            cards = self.cards

        (_, counts) = self.count_cards_colors(cards)
        return max(counts.values())

    def contains_creature(self, slot_name: Optional[str] = None) -> bool:
        if slot_name is not None:
            cards = self.content[slot_name]["cards"]
        else:
            cards = self.cards

        for card in cards:
            if "Creature" in card.card.types:
                return True
        return False

    async def get_images(
        self, size: str = "normal", foil: Optional[bool] = None
    ) -> Sequence[np.ndarray]:
        img = [await c.get_image(size, foil) for c in self.cards]
        return img

    def json(self) -> Sequence[dict]:
        return [card.json() for card in self.cards]

    def arena_format(self) -> str:
        return "\n".join([card.arena_format() for card in self.cards])

    def __str__(self) -> str:
        return "\n".join([str(card) for card in self.cards])
