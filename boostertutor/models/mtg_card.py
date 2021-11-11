#!/usr/bin/env python

import os

import aiofiles
import aiohttp
import imageio


class MtgCard:
    def __init__(self, card, foil=False):
        self.card = card
        self.foil = foil

    def mana(self):
        colors = ["W", "U", "B", "R", "G"]

        if hasattr(self.card, "manaCost"):
            cost = self.card.manaCost.lstrip("{").rstrip("}").split("}{")
            mana = [c for c in colors if c in cost]
            if not mana:
                hybrid = []
                for symbol in cost:
                    if "/" in symbol:
                        hybrid.extend(symbol.split("/"))
                hybrid_colors = [c for c in colors if c in hybrid]
                if len(hybrid_colors) == 2:
                    mana = [hybrid_colors[0] + hybrid_colors[1]]
                else:
                    mana = hybrid_colors
        else:
            mana = self.card.colors
        return mana

    async def get_image(self, size="normal", foil=None):
        sizes = ["large", "normal", "small"]
        assert size in sizes

        scry_id = self.card.identifiers["scryfallId"]
        img_url = (
            f"https://api.scryfall.com/cards/{scry_id}"
            f"?format=image&version={size}"
        )
        if foil is None:
            foil = self.foil

        async with aiohttp.ClientSession() as session:
            async with session.get(img_url) as resp:
                resp.raise_for_status()
                resp_bytes = await resp.read()

        im = imageio.imread(resp_bytes)

        if foil:
            foil_path = os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                "..",
                "img",
                f"foil_{size}.png",
            )
            async with aiofiles.open(foil_path, "rb") as f:
                content = await f.read()
            foil = imageio.imread(content)[:, :, 0:3]

            im = (im * 0.7 + foil * 0.3).astype("uint8")

        return im

    def get_json(self):
        return {"name": f"{self.card.name}", "count": 1}

    def get_arena_format(self):
        if (
            self.card.setCode != "STA"
            and hasattr(self.card, "promoTypes")
            and hasattr(self.card, "variations")
        ):
            number = self.card.variations[0].number
        else:
            number = self.card.number
        return f"1 {self.card.name} ({self.card.setCode}) {number}"

    def pack_sort_key(self):
        r = ["mythic", "rare", "uncommon", "common", "special"]
        is_common_land = (
            "Land" in self.card.types and self.card.rarity == "common"
        )
        return (is_common_land, self.foil, r.index(self.card.rarity))

    def __eq__(self, other):
        return self.card == other.card

    def __lt__(self, other):
        return self < other

    def __str__(self):
        foil_str = " (foil)" if self.foil else ""
        return f"{self.card.name} ({self.card.setCode}){foil_str}"

    def __repr__(self):
        return f"<boostertutor.models.mtg_card.MtgCard: {str(self)}>"
