import logging
from collections import Counter
from typing import Any, Literal, Optional, Sequence, Tuple

from numpy.random import choice

from boostertutor.models.mtg_card import MtgCard
from boostertutor.models.mtg_pack import MtgPack
from boostertutor.models.mtgjson_sql import (
    BoosterMeta,
    BoosterType,
    BoosterVariationMeta,
    CardDb,
    SetMeta,
    SheetCardMeta,
)
from boostertutor.utils.utils import jmp_deck_name_to_str

logger = logging.getLogger(__name__)


class MtgPackGenerator:
    def __init__(
        self,
        path_to_mtgjson: str = "data/AllPrintings.sqlite",
        max_balancing_iterations: int = 100,
        validate_data: bool = True,
    ) -> None:
        self.max_balancing_iterations = max_balancing_iterations
        self.data = CardDb(path_to_mtgjson)
        self.sets_with_boosters: list[str] = [
            set_code
            for set_code, set in self.data.sets.items()
            if set.boosters and set_code not in ["JMP", "J22", "J25", "CLU"]
        ]
        self.sets_with_decks: list[str] = ["JMP", "J22", "J25"]
        self.override_play_booster_balance()
        if validate_data:
            self.validate_booster_data()

    def validate_booster_data(self) -> int:
        logger.info("Booster data validation starting...")
        num_warnings = 0
        for set_code in self.sets_with_boosters:
            set = self.data.sets[set_code]
            for booster_name, booster in set.boosters.items():
                for sheet in booster.sheets:
                    for card in sheet.cards:
                        if card._uuid not in self.data.cards_by_id:
                            logger.warning(
                                f"Found non-existent card id in a booster: "
                                f"{set_code} {booster_name} {sheet.name} "
                                f"{card._uuid}"
                            )
                            num_warnings += 1
        if num_warnings:
            logger.warning(
                "Generating boosters with non-existent card ids will result "
                "in exceptions. Please consider reporting the non-existent "
                "ids to the MTGJSON devs."
            )
        logger.info("Concluded booster data validation.")
        return num_warnings

    def get_set_booster_meta_pair(
        self, set: str, booster_type: Optional[BoosterType] = None
    ) -> Tuple[SetMeta, BoosterMeta]:
        s = set.upper()
        b_type = booster_type

        # Validate Arena only sets
        if s.startswith("A-"):
            s = s.removeprefix("A-")
            assert b_type is None or b_type in [
                BoosterType.DRAFT_ARENA,
                BoosterType.PLAY_ARENA,
            ], f"Booster type {b_type} not available for set A-{s}"
            b_type = BoosterType.DRAFT_ARENA

        # Validate set meta exists
        set_meta = self.data.sets.get(s)
        assert set_meta is not None, f"No booster for set code {s} exist."

        # Select correct booster_meta
        boosters = set_meta.boosters
        if b_type:
            if b_type not in boosters:
                if (
                    b_type == BoosterType.DRAFT_ARENA
                    and BoosterType.PLAY_ARENA in boosters
                ):
                    b_type = BoosterType.PLAY_ARENA
                else:
                    raise ValueError(
                        f"Booster type {b_type} not available for set {s}"
                    )
        elif s == "SIR":
            b_type = choice(
                [
                    BoosterType.ARENA_1,
                    BoosterType.ARENA_2,
                    BoosterType.ARENA_3,
                    BoosterType.ARENA_4,
                ]
            )
        elif s == "PIO":
            b_type = choice(
                [
                    BoosterType.ARENA_1,
                    BoosterType.ARENA_2,
                    BoosterType.ARENA_3,
                ]
            )
        elif BoosterType.DRAFT in boosters:
            b_type = BoosterType.DRAFT
        elif BoosterType.PLAY in boosters:
            b_type = BoosterType.PLAY
        elif BoosterType.DEFAULT in boosters:
            b_type = BoosterType.DEFAULT
        else:
            b_type = next(iter(boosters))
            logger.warning(
                f"No expected booster type found for set {s}, {b_type.value} "
                "used."
            )

        assert b_type, "Unexpected None booster_type after validation"
        return (set_meta, boosters[b_type])

    def get_packs(
        self,
        set: str,
        n: int = 1,
        balance: bool = True,
        booster_type: Optional[BoosterType] = None,
    ) -> Sequence[MtgPack]:
        return [
            self.get_pack(set, balance=balance, booster_type=booster_type)
            for _ in range(n)
        ]

    def get_pack(
        self,
        set: str,
        balance: bool = True,
        booster_type: Optional[BoosterType] = None,
    ) -> MtgPack:
        logger.debug(f"Generating {set.upper()} pack...")
        iterations = self.max_balancing_iterations if balance else 1
        return self._get_pack_internal(
            set, iterations, booster_type=booster_type
        )

    def _get_pack_internal(
        self,
        set: str,
        iterations: int,
        booster_type: Optional[BoosterType] = None,
    ) -> MtgPack:
        set_meta, booster_meta = self.get_set_booster_meta_pair(
            set, booster_type
        )

        boosters_p = [
            v.weight / booster_meta.total_weight
            for v in booster_meta.variations
        ]

        v_index: int = choice(len(booster_meta.variations), p=boosters_p)
        booster_content = booster_meta.variations[v_index].content

        pack_content = {}

        balance = False
        for content in booster_content:
            sheet = content.sheet
            if sheet.balance_colors:
                balance = balance or sheet.balance_colors
                num_of_backups = 20
            else:
                num_of_backups = 0

            cards_p = [x.weight / sheet.total_weight for x in sheet.cards]

            picks: list[SheetCardMeta] = choice(
                sheet.cards,
                size=content.num_picks + num_of_backups,
                replace=False,
                p=cards_p,
            )

            pick_i = 0
            slot_content: list[MtgCard] = []
            slot_backup: list[MtgCard] = []
            for card in picks:
                if pick_i < content.num_picks:
                    slot_content.append(MtgCard(card.data, sheet.is_foil))
                else:
                    slot_backup.append(MtgCard(card.data, sheet.is_foil))
                pick_i += 1

            slot: dict[str, Any] = {"cards": slot_content}
            slot["balance"] = sheet.balance_colors
            if num_of_backups:
                slot["backups"] = slot_backup

            pack_content[sheet.name] = slot

        pack = MtgPack(
            pack_content,
            set=set_meta,
            name=set_meta.name,
            type=booster_meta.name,
        )

        if not balance:
            logger.debug("Pack should not be balanced, skipping.")
            iterations = 1

        if iterations <= 1 or pack.is_balanced(rebalance=True):
            logger.info(
                f"{set_meta.code} {booster_meta.name} pack generated, "
                f"iterations needed: "
                f"{str(self.max_balancing_iterations - iterations + 1)}"
            )
            return pack
        else:
            return self._get_pack_internal(
                set_meta.code, iterations - 1, booster_type=booster_meta.name
            )

    def get_random_packs(
        self,
        sets: Optional[Sequence[str]] = None,
        n: int = 1,
        replace: bool = False,
        balance: bool = True,
        booster_type: Optional[BoosterType] = None,
    ) -> Sequence[MtgPack]:
        if sets is None:
            sets = self.sets_with_boosters

        assert replace or n <= len(sets)

        boosters: list[str] = choice(sets, size=n, replace=replace)
        return [
            self.get_pack(set=b, balance=balance, booster_type=booster_type)
            for b in boosters
        ]

    def get_random_arena_jmp_decks(
        self, n: int = 1, replace: bool = True
    ) -> Sequence[MtgPack]:
        m21 = self.data.sets["M21"]
        ajmp = self.data.sets["AJMP"]
        replacements = {
            "Chain Lightning": "Lightning Strike",
            "Lightning Bolt": "Lightning Strike",
            "Ball Lightning": "Lightning Serpent",
            "Ajani's Chosen": "Archon of Sun's Grace",
            "Angelic Arbiter": "Serra's Guardian",
            "Draconic Roar": "Scorching Dragonfire",
            "Goblin Lore": "Goblin Oriflamme",
            "Flametongue Kavu": "Fanatic of Mogis",
            "Exhume": "Bond of Revival",
            "Fa'adiyah Seer": "Dryad Greenseeker",
            "Mausoleum Turnkey": "Audacious Thief",
            "Path to Exile": "Banishing Light",
            "Read the Runes": "Gadwick, the Wizened",
            "Reanimate": "Doomed Necromancer",
            "Rhystic Study": "Teferi's Ageless Insight",
            "Sheoldred, Whispering One": "Carnifex Demon",
            "Scourge of Nel Toth": "Woe Strider",
            "Scrounging Bandar": "Pollenbright Druid",
            "Thought Scour": "Weight of Memory",
            "Time to Feed": "Prey Upon",
        }

        p_list = self.get_random_decks(set="JMP", n=n, replace=replace)
        for p in p_list:
            for i, c in enumerate(p.content["deck"]["cards"]):
                if c.meta.name in replacements:
                    r = replacements[c.meta.name]
                    r_card = (
                        m21.card_by_name(r)
                        if m21.card_by_name(r)
                        else ajmp.card_by_name(r)
                    )
                    assert r_card
                    card = MtgCard(r_card, foil=c.foil)
                    card.meta.set_code = "JMP"
                    p.content["deck"]["cards"][i] = card

        return p_list

    def get_random_decks(
        self, set: str, n: int = 1, replace: bool = True
    ) -> Sequence[MtgPack]:
        assert set.upper() in self.sets_with_decks
        set_meta = self.data.sets.get(set.upper())
        assert set_meta is not None
        all_decks = set_meta.boosters[BoosterType.JUMPSTART].variations
        decks: list[BoosterVariationMeta] = choice(
            all_decks, size=n, replace=replace
        )
        packs = []
        for d in decks:
            logger.debug(f"Generating {set.upper()} deck...")
            cards: list[MtgCard] = []
            sheet = d.content[0].sheet
            for c in sheet.cards:
                for _ in range(c.weight):
                    cards.append(MtgCard(c.data, foil=sheet.is_foil))
            content = {"deck": {"cards": cards, "balance": False}}
            packs.append(
                MtgPack(
                    content,
                    set=set_meta,
                    name=jmp_deck_name_to_str(sheet.name),
                    type=BoosterType.JUMPSTART,
                )
            )
            logger.info(f"{sheet.name} ({set.upper()}) deck generated")
        return packs

    def get_cube_packs(self, cube: dict, n: int = 1) -> Sequence[MtgPack]:
        return [self.get_cube_pack(cube) for _ in range(n)]

    def get_cube_pack(self, cube: dict) -> MtgPack:
        logger.debug(f"Generating {cube['shortId']} cube pack...")
        cube_name = cube["name"]
        try:
            slots = []
            for slot in cube["formats"][0]["packs"][0]["slots"]:
                assert slot.startswith("tag:") or slot.startswith("t:")
                slots.append(slot.split(":")[1].strip('"'))
            pack_format: dict[str, int] = Counter(slots)
            logger.debug(f"Pack format: {pack_format}")

            replace = cube["formats"][0]["multiples"]

            cube_cards: dict[str, list[str]] = {key: [] for key in pack_format}
            for card in cube["cards"]["mainboard"]:
                if card["tags"]:
                    for tag in card["tags"]:
                        if tag in cube_cards:
                            cube_cards[tag].append(card)
        except (KeyError, IndexError, AssertionError) as e:
            logger.debug(e, exc_info=True)
            pack_format = {"cards": 15}
            replace = False
            cube_cards = {"cards": cube["cards"]["mainboard"]}
        logger.debug(f"Using pack format: {pack_format}")

        pack_list: list[dict[str, Any]] = []
        for key, num in pack_format.items():
            pack_list.extend(choice(cube_cards[key], num, replace=replace))

        pack_cards: list[MtgCard] = []
        for card_dict in pack_list:
            card_data = self.data.get_card_by_scryfall_id(card_dict["cardID"])
            if card_data:
                pack_cards.append(
                    MtgCard(
                        card_data,
                        foil=card_dict.get("finish", "Non-foil") != "Non-foil",
                    )
                )

        logger.info(f"{cube['shortId']} cube pack generated")
        return MtgPack(
            {"pack": {"cards": pack_cards, "balance": False}},
            name=cube_name,
            type=BoosterType.CUBE,
        )

    async def get_pack_ev(
        self,
        set: str,
        currency: Literal["eur", "usd"],
        eur_usd_rate: Optional[float] = None,
        bulk_threshold: float = 0.0,
        booster_type: Optional[BoosterType] = None,
    ) -> float:
        _, booster_meta = self.get_set_booster_meta_pair(set, booster_type)
        sheets_ev: dict[str, float] = {}
        for sheet_meta in booster_meta.sheets:
            sheet_total = 0.0
            for sheet_card in sheet_meta.cards:
                card = MtgCard(sheet_card.data, sheet_meta.is_foil)
                price = await card.get_price(currency, eur_usd_rate)
                if price and price >= bulk_threshold:
                    sheet_total += price * sheet_card.weight
            sheets_ev[sheet_meta.name] = sheet_total / sheet_meta.total_weight

        booster_ev = 0.0
        for composition in booster_meta.variations:
            composition_ev = sum(
                [
                    sheets_ev[content.sheet.name] * content.num_picks
                    for content in composition.content
                ]
            )
            booster_ev += (
                composition_ev * composition.weight / booster_meta.total_weight
            )
        return round(booster_ev, 2)

    def fix_missing_balance(
        self,
        set: str,
        sheet_name: str,
        booster_type: BoosterType = BoosterType.DRAFT,
    ) -> None:
        sheets = self.data.sets[set.upper()].boosters[booster_type].sheets
        commons = next(
            (sheet for sheet in sheets if sheet.name == sheet_name), None
        )
        if not commons:
            logger.error(
                f"`generator.fix_missing_balance({set}, {sheet_name})` did "
                f"not find sheet '{sheet_name}' in {set}."
            )
        elif commons.balance_colors:
            logger.warning(
                f"`generator.fix_missing_balance({set}, {sheet_name})` call "
                f"can be removed. Common sheet doesn't need to be fixed "
                f"anymore."
            )
        else:
            commons.balance_colors = True

    def remove_broken_set(self, set: str) -> None:
        self.sets_with_boosters.remove(set.upper())
        logger.warning(
            f"Removed {set.upper()} from available sets because broken."
        )

    def override_play_booster_balance(self) -> None:
        self.fix_missing_balance(
            "fin", "common", booster_type=BoosterType.PLAY
        )
        self.fix_missing_balance(
            "tdm", "common", booster_type=BoosterType.PLAY
        )
        self.fix_missing_balance(
            "dft", "common", booster_type=BoosterType.PLAY
        )
        self.fix_missing_balance(
            "pio", "common", booster_type=BoosterType.ARENA_1
        )
        self.fix_missing_balance(
            "pio", "common", booster_type=BoosterType.ARENA_2
        )
        self.fix_missing_balance(
            "pio", "common", booster_type=BoosterType.ARENA_3
        )
        self.fix_missing_balance(
            "fdn", "common", booster_type=BoosterType.PLAY
        )
        self.fix_missing_balance(
            "dsk", "common", booster_type=BoosterType.PLAY
        )
        self.fix_missing_balance(
            "blb", "common", booster_type=BoosterType.PLAY
        )
        self.fix_missing_balance(
            "mh3", "common", booster_type=BoosterType.PLAY
        )
        self.fix_missing_balance(
            "otj", "common", booster_type=BoosterType.PLAY
        )
        self.fix_missing_balance(
            "mkm", "commonWithShowcase", booster_type=BoosterType.PLAY
        )
        self.fix_missing_balance(
            "mkm", "common", booster_type=BoosterType.PLAY_ARENA
        )
