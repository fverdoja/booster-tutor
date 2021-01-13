#!/usr/bin/env python
import aiohttp
import aiofiles
import imageio
import os


class MtgCard:
    def __init__(self, card, foil=False):
        self.card = card
        self.foil = foil

    async def get_image(self, size="normal", foil=None):
        sizes = ["large", "normal", "small"]
        assert(size in sizes)

        scry_id = self.card.identifiers["scryfallId"]
        img_url = f"https://api.scryfall.com/cards/{scry_id}" \
                  f"?format=image&version={size}"
        if foil is None:
            foil = self.foil

        async with aiohttp.ClientSession() as session:
            async with session.get(img_url) as resp:
                resp.raise_for_status()
                resp_bytes = await resp.read()

        im = imageio.imread(resp_bytes)

        if foil:
            foil_path = os.path.join(os.path.dirname(
                os.path.realpath(__file__)), "..", "img", f"foil_{size}.png")
            async with aiofiles.open(foil_path, "rb") as f:
                content = await f.read()
            foil = imageio.imread(content)[:, :, 0:3]

            im = (im * 0.7 + foil * 0.3).astype("uint8")

        return im

    def get_arena_format(self):
        return f"1 {self.card.name} ({self.card.setCode}) {self.card.number}"

    def to_str(self):
        foil_str = " (foil)" if self.foil else ""
        return f"{self.card.name}{foil_str}"

    def pack_sort_key(self):
        r = ["mythic", "rare", "uncommon", "common"]
        is_basic = "Basic" in self.card.supertypes
        return (is_basic, self.foil, r.index(self.card.rarity))

    def __eq__(self, other):
        return self.card == other.card

    def __lt__(self, other):
        return self < other
