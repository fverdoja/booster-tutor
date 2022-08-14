import logging
from collections import Counter
from typing import Optional, Sequence

from numpy.random import choice

from boostertutor.models.mtg_card import MtgCard
from boostertutor.models.mtg_pack import MtgPack
from boostertutor.models.mtgjson import CardDb

logger = logging.getLogger(__name__)


class MtgPackGenerator:
    def __init__(
        self,
        path_to_mtgjson: str = "data/AllPrintings.json",
        path_to_jmp: Optional[str] = None,
        jmp_arena: bool = False,
        max_balancing_iterations: int = 100,
    ) -> None:
        self.max_balancing_iterations = max_balancing_iterations
        self.data = CardDb.from_file(path_to_mtgjson)
        self.has_jmp = False
        if path_to_jmp is not None:
            self.import_jmp(path_to_jmp, arena=jmp_arena)
        self.fix_iko()
        self.sets_with_boosters = [
            set_code
            for set_code, set in self.data.sets.items()
            if hasattr(set, "booster")
        ]
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
        self, set: str, n: int = 1, balance: bool = True
    ) -> Sequence[MtgPack]:
        return [self.get_pack(set, balance=balance) for _ in range(n)]

    def get_pack(self, set: str, balance: bool = True) -> MtgPack:
        logger.debug(f"Generating {set.upper()} pack...")
        iterations = self.max_balancing_iterations if balance else 1
        return self._get_pack_internal(set, iterations)

    def _get_pack_internal(self, set: str, iterations: int) -> MtgPack:
        assert set.upper() in self.data.sets

        booster = self.data.sets[set.upper()].booster
        if "default" in booster:
            booster_meta = booster["default"]
        elif "arena" in booster:
            booster_meta = booster["arena"]
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

            slot = {"cards": slot_content}
            slot["balance"] = (
                "balanceColors" in sheet_meta.keys()  # type: ignore
            )
            if num_of_backups:
                slot["backups"] = slot_backup

            pack_content[sheet_name] = slot

        pack_name = booster_meta.get("name", None)

        pack = MtgPack(pack_content, name=pack_name)

        if not balance:
            logger.debug("Pack should not be balanced, skipping.")
            iterations = 1

        if iterations <= 1 or pack.is_balanced(rebalance=True):
            logger.info(
                f"{set.upper()} pack generated, iterations needed: "
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
    ) -> Sequence[MtgPack]:
        if sets is None:
            sets = self.sets_with_boosters

        assert replace or n <= len(sets)

        boosters = choice(sets, size=n, replace=replace)
        return [self.get_pack(set=b, balance=balance) for b in boosters]

    def get_random_jmp_decks(
        self, n: int = 1, replace: bool = True
    ) -> Sequence[MtgPack]:
        assert self.has_jmp
        jmp_decks = self.data.sets["JMP"].decks
        decks = choice(jmp_decks, size=n, replace=replace)
        packs = []
        for d in decks:
            logger.debug("Generating JMP pack...")
            cards = [MtgCard(c) for c in d["mainBoard"]]
            content = {"deck": {"cards": cards, "balance": False}}
            packs.append(
                MtgPack(content, set=self.data.sets["JMP"], name=d["name"])
            )
            logger.info(f"{d['name']} (JMP) pack generated")
        return packs

    def get_cube_packs(self, cube: dict, n: int = 1) -> Sequence[MtgPack]:
        return [self.get_cube_pack(cube) for _ in range(n)]

    def get_cube_pack(self, cube: dict) -> MtgPack:
        logger.debug(f"Generating {cube['shortID']} cube pack...")
        cube_name = cube["name"]
        try:
            slots = []
            for slot in cube["draft_formats"][0]["packs"][0]["slots"]:
                assert slot.startswith("tag:") or slot.startswith("t:")
                slots.append(slot.split(":")[1].strip('"'))
            pack_format: dict[str, int] = Counter(slots)

            replace = cube["draft_formats"][0]["multiples"]

            cube_cards: dict[str, list[str]] = {key: [] for key in pack_format}
            for card in cube["cards"]:
                tag = card["tags"][0]
                if tag in cube_cards:
                    cube_cards[tag].append(card)
        except (KeyError, IndexError, AssertionError):
            pack_format = {"cards": 15}
            replace = False
            cube_cards = {"cards": cube["cards"]}
        logger.debug(f"Using pack format: {pack_format}")

        pack_list = []
        for key, num in pack_format.items():
            pack_list.extend(choice(cube_cards[key], num, replace=replace))

        pack_cards = [
            MtgCard(
                self.data.cards_by_scryfall_id[card_dict["cardID"]],
                foil=card_dict["finish"] != "Non-foil",
            )
            for card_dict in pack_list
        ]
        logger.info(f"{cube['shortID']} cube pack generated")
        return MtgPack(
            {"pack": {"cards": pack_cards, "balance": False}}, name=cube_name
        )

    async def get_pack_ev(
        self,
        set: str,
        currency: str,
        eur_usd_rate: Optional[float] = None,
        bulk_threshold: float = 0.0,
    ) -> float:
        assert set.upper() in self.data.sets
        booster = self.data.sets[set.upper()].booster
        if "default" in booster:
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

    def fix_iko(self) -> None:
        iko = self.data.sets["IKO"]
        iko.booster["default"]["sheets"]["common"]["balanceColors"] = True

    def import_jmp(self, path_to_jmp: str, arena: bool = False) -> None:
        self.data.add_decks_from_folder(path_to_jmp + "decks/")
        if arena:
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
            m21 = self.data.sets["M21"].cards_by_name
            ajmp = self.data.sets["AJMP"].cards_by_name
            for d in self.data.sets["JMP"].decks:
                for i, c in enumerate(d["mainBoard"]):
                    if c.name in replacements:
                        r = replacements[c.name]
                        if r in m21:
                            card = m21[r]
                        else:
                            card = ajmp[r]
                            card.setCode = "JMP"
                        d["mainBoard"][i] = card
        self.has_jmp = True
