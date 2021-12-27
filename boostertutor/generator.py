import logging
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
        self.sets_with_boosters = []
        for s in self.data.sets:
            if hasattr(self.data.sets[s], "booster"):
                self.sets_with_boosters.append(s)

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
