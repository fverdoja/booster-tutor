import logging
from collections import Counter
from typing import Any, Optional, Sequence

from numpy.random import choice

from boostertutor.models.mtg_card import MtgCard
from boostertutor.models.mtg_pack import MtgPack
from boostertutor.models.mtgjson import CardDb

logger = logging.getLogger(__name__)


class MtgPackGenerator:
    def __init__(
        self,
        path_to_mtgjson: str = "data/AllPrintings.json",
        max_balancing_iterations: int = 100,
        validate_data: bool = True,
    ) -> None:
        self.max_balancing_iterations = max_balancing_iterations
        self.data = CardDb.from_file(path_to_mtgjson)
        self.sets_with_boosters: list[str] = [
            set_code
            for set_code, set in self.data.sets.items()
            if hasattr(set, "booster") and set_code not in ["JMP", "J22"]
        ]
        self.sets_with_decks: list[str] = ["JMP", "J22"]
        if validate_data:
            self.validate_booster_data()

    def validate_booster_data(self) -> int:
        num_warnings = 0
        for set_code in self.sets_with_boosters:
            set = self.data.sets[set_code]
            for booster_name, booster in set.booster.items():
                for sheet_name, sheet in booster["sheets"].items():
                    for id in sheet["cards"]:
                        if id not in self.data.cards_by_id:
                            logger.warning(
                                f"Found non-existent card id in a booster: "
                                f"{set_code} {booster_name} {sheet_name} {id}"
                            )
                            num_warnings += 1
        if num_warnings:
            logger.warning(
                "Generating boosters with non-existent card ids will result "
                "in exceptions. Please consider reporting the non-existent "
                "ids to the MTGJSON devs."
            )
        return num_warnings

    def get_packs(
        self,
        set: str,
        n: int = 1,
        balance: bool = True,
        booster_type: Optional[str] = None,
    ) -> Sequence[MtgPack]:
        return [
            self.get_pack(set, balance=balance, booster_type=booster_type)
            for _ in range(n)
        ]

    def get_pack(
        self,
        set: str,
        balance: bool = True,
        booster_type: Optional[str] = None,
    ) -> MtgPack:
        logger.debug(f"Generating {set.upper()} pack...")
        iterations = self.max_balancing_iterations if balance else 1
        return self._get_pack_internal(
            set, iterations, booster_type=booster_type
        )

    def _get_pack_internal(
        self, set: str, iterations: int, booster_type: Optional[str] = None
    ) -> MtgPack:
        set_meta = self.data.sets.get(set.upper())
        assert set_meta is not None

        booster = set_meta.booster
        if booster_type:
            if booster_type.lower() not in booster:
                raise ValueError(
                    f"Booster type {booster_type} not available for set {set}"
                )
        elif set.upper() == "SIR":
            booster_type = choice(["arena-1", "arena-2", "arena-3", "arena-4"])
        elif "default" in booster:
            booster_type = "default"
        elif "arena" in booster:
            booster_type = "arena"
        else:
            booster_type = next(iter(booster))
        booster_meta = booster[booster_type]

        boosters_p = [
            x["weight"] / booster_meta["boostersTotalWeight"]
            for x in booster_meta["boosters"]
        ]

        booster = booster_meta["boosters"][
            choice(len(booster_meta["boosters"]), p=boosters_p)
        ]["contents"]

        pack_content = {}

        balance = False
        for sheet_name, k in booster.items():
            sheet_meta = booster_meta["sheets"][sheet_name]
            if "balanceColors" in sheet_meta.keys():
                balance = balance or sheet_meta["balanceColors"]
                num_of_backups = 20
            else:
                num_of_backups = 0

            cards = list(sheet_meta["cards"].keys())
            cards_p = [
                x / sheet_meta["totalWeight"]
                for x in sheet_meta["cards"].values()
            ]

            picks = choice(
                cards, size=k + num_of_backups, replace=False, p=cards_p
            )

            pick_i = 0
            slot_content = []
            slot_backup = []
            for card_id in picks:
                if pick_i < k:
                    slot_content.append(
                        MtgCard(
                            self.data.cards_by_id[card_id], sheet_meta["foil"]
                        )
                    )
                else:
                    slot_backup.append(
                        MtgCard(
                            self.data.cards_by_id[card_id], sheet_meta["foil"]
                        )
                    )
                pick_i += 1

            slot: dict[str, Any] = {"cards": slot_content}
            slot["balance"] = "balanceColors" in sheet_meta.keys()
            if num_of_backups:
                slot["backups"] = slot_backup

            pack_content[sheet_name] = slot

        pack_name = booster_meta.get("name", None)

        pack = MtgPack(pack_content, set=set_meta, name=pack_name)

        if not balance:
            logger.debug("Pack should not be balanced, skipping.")
            iterations = 1

        if iterations <= 1 or pack.is_balanced(rebalance=True):
            logger.info(
                f"{set.upper()} {booster_type} pack generated, iterations "
                f"needed: "
                f"{str(self.max_balancing_iterations - iterations + 1)}"
            )
            return pack
        else:
            return self._get_pack_internal(set, iterations - 1)

    def get_random_packs(
        self,
        sets: Optional[Sequence[str]] = None,
        n: int = 1,
        replace: bool = False,
        balance: bool = True,
        booster_type: Optional[str] = None,
    ) -> Sequence[MtgPack]:
        if sets is None:
            sets = self.sets_with_boosters

        assert replace or n <= len(sets)

        boosters = choice(sets, size=n, replace=replace)
        return [
            self.get_pack(set=b, balance=balance, booster_type=booster_type)
            for b in boosters
        ]

    def get_random_arena_jmp_decks(
        self, n: int = 1, replace: bool = True
    ) -> Sequence[MtgPack]:
        m21 = self.data.sets["M21"].cards_by_name
        ajmp = self.data.sets["AJMP"].cards_by_name
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
                if c.card.name in replacements:
                    r = replacements[c.card.name]
                    if r in m21:
                        card = MtgCard(m21[r], foil=c.foil)
                    else:
                        card = MtgCard(ajmp[r], foil=c.foil)
                        card.card.setCode = "JMP"
                    p.content["deck"]["cards"][i] = card

        return p_list

    def get_random_decks(
        self, set: str, n: int = 1, replace: bool = True
    ) -> Sequence[MtgPack]:
        assert set.upper() in self.sets_with_decks
        set_meta = self.data.sets.get(set.upper())
        assert set_meta is not None
        all_decks = set_meta.decks
        decks = choice(all_decks, size=n, replace=replace)
        packs = []
        for d in decks:
            logger.debug(f"Generating {set.upper()} pack...")
            cards: list[MtgCard] = []
            for c in d["mainBoard"]:
                n = c.get("count", 1)
                for _ in range(n):
                    cards.append(
                        MtgCard(
                            self.data.cards_by_id[c["uuid"]],
                            foil=c.get("finish", "nonfoil") != "nonfoil",
                        )
                    )
            content = {"deck": {"cards": cards, "balance": False}}
            packs.append(MtgPack(content, set=set_meta, name=d["name"]))
            logger.info(f"{d['name']} ({set.upper()}) pack generated")
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
                if card["tags"] and card["tags"][0] in cube_cards:
                    cube_cards[card["tags"][0]].append(card)
        except (KeyError, IndexError, AssertionError) as e:
            logger.debug(e, exc_info=True)
            pack_format = {"cards": 15}
            replace = False
            cube_cards = {"cards": cube["cards"]["mainboard"]}
        logger.debug(f"Using pack format: {pack_format}")

        pack_list: list[dict[str, Any]] = []
        for key, num in pack_format.items():
            pack_list.extend(choice(cube_cards[key], num, replace=replace))

        pack_cards = [
            MtgCard(
                self.data.cards_by_scryfall_id[card_dict["cardID"]],
                foil=card_dict.get("finish", "Non-foil") != "Non-foil",
            )
            for card_dict in pack_list
        ]
        logger.info(f"{cube['shortId']} cube pack generated")
        return MtgPack(
            {"pack": {"cards": pack_cards, "balance": False}}, name=cube_name
        )

    async def get_pack_ev(
        self,
        set: str,
        currency: str,
        eur_usd_rate: Optional[float] = None,
        bulk_threshold: float = 0.0,
        booster_type: Optional[str] = None,
    ) -> float:
        assert set.upper() in self.data.sets
        booster = self.data.sets[set.upper()].booster
        if booster_type:
            if booster_type.lower() in booster:
                booster_meta = booster[booster_type.lower()]
            else:
                raise ValueError(
                    f"Booster type {booster_type} not available for set {set}"
                )
        elif "default" in booster:
            booster_meta = booster["default"]
        else:
            logger.warning(
                f"Requested EV of {set.upper()} booster, but no "
                f"paper booster metadata found for it. Returning 0."
            )
            return 0
        sheets_ev = {}
        for sheet_name, sheet_meta in booster_meta["sheets"].items():
            total_weight = sheet_meta["totalWeight"]
            foil = sheet_meta["foil"]
            sheet_total = 0.0
            for card_id, weight in sheet_meta["cards"].items():
                card = MtgCard(self.data.cards_by_id[card_id], foil)
                price = await card.get_price(currency, eur_usd_rate)
                if price and price >= bulk_threshold:
                    sheet_total += price * weight
            sheets_ev[sheet_name] = sheet_total / total_weight

        booster_ev = 0.0
        booster_total_weight = booster_meta["boostersTotalWeight"]
        for composition in booster_meta["boosters"]:
            weight = composition["weight"]
            composition_ev = sum(
                [
                    sheets_ev[sheet_name] * count
                    for sheet_name, count in composition["contents"].items()
                ]
            )
            booster_ev += composition_ev * weight / booster_total_weight
        return round(booster_ev, 2)

    def fix_missing_balance(self, set: str, sheet: str) -> None:
        commons: dict[str, Any] = self.data.sets[set.upper()].booster[
            "default"
        ]["sheets"][sheet]
        if commons.get("balanceColors"):
            logger.warning(
                f"`generator.fix_missing_balance({set}, {sheet})` function "
                f"can be removed. Common sheet doesn't need to be fixed "
                f"anymore."
            )
        else:
            commons["balanceColors"] = True

    def remove_broken_set(self, set: str) -> None:
        self.sets_with_boosters.remove(set.upper())
        logger.warning(
            f"Removed {set.upper()} from available sets because broken."
        )
