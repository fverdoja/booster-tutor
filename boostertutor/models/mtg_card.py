from aiohttp_client_cache.session import CachedSession
from aiohttp_client_cache.backends.sqlite import SQLiteBackend
from datetime import timedelta
from typing import Optional

import imageio
import numpy as np

from boostertutor.models.mtgjson_sql import CardProxy
from boostertutor.utils.utils import foil_layer

SCRYFALL_CARD_BASE_URL = "https://api.scryfall.com/cards"

cache = SQLiteBackend(
    cache_name=".aiohttp_cache/scryfall.sqlite",
    urls_expire_after={
        f"{SCRYFALL_CARD_BASE_URL}/*?format=image*": timedelta(days=30),
        f"{SCRYFALL_CARD_BASE_URL}/*": timedelta(days=1),
    },
)


class MtgCard:
    def __init__(self, card: CardProxy, foil: bool = False) -> None:
        self.card = card
        self.foil = foil

    def mana(self) -> list[str]:
        colors = ["W", "U", "B", "R", "G"]

        if self.card.mana_cost:
            cost = self.card.mana_cost.lstrip("{").rstrip("}").split("}{")
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

    async def get_price(
        self, currency: str, eur_usd_rate: Optional[float] = None
    ) -> Optional[float]:
        currencies = ("eur", "usd")
        assert currency in currencies
        alt_currency = currencies[1 - currencies.index(currency)]
        if self.foil:
            currency += "_foil"
            alt_currency += "_foil"

        scry_id = self.card.identifiers.scryfall_id
        card_url = f"{SCRYFALL_CARD_BASE_URL}/{scry_id}"

        async with CachedSession(cache=cache) as session:
            async with session.get(card_url) as resp:
                resp.raise_for_status()
                card = await resp.json()

        price = card["prices"][currency]
        if price is not None:
            price = float(price)
        elif (
            card["prices"][alt_currency] is not None
            and eur_usd_rate is not None
        ):
            if alt_currency.startswith("usd"):
                price = float(card["prices"][alt_currency]) / eur_usd_rate
            else:
                price = float(card["prices"][alt_currency]) * eur_usd_rate
        return price

    async def get_image(
        self, size: str = "normal", foil: Optional[bool] = None
    ) -> np.ndarray:
        sizes = ["large", "normal", "small", "png", "border_crop"]
        assert size in sizes

        scry_id = self.card.identifiers.scryfall_id
        img_url = (
            f"{SCRYFALL_CARD_BASE_URL}/{scry_id}?format=image&version={size}"
        )
        if foil is None:
            foil = self.foil

        async with CachedSession(cache=cache) as session:
            async with session.get(img_url) as resp:
                resp.raise_for_status()
                resp_bytes = await resp.read()

        im: np.ndarray = imageio.imread(resp_bytes)

        if foil:
            foil_im = foil_layer(size=im.shape[0:2])
            im[..., 0:3] = (im[..., 0:3] * 0.7 + foil_im * 0.3).astype("uint8")

        return im

    def json(self) -> dict:
        name = (
            self.card.name
            if self.card.layout != "meld"
            else self.card.face_name
        )
        return {"name": f"{name}", "count": 1}

    def arena_format(self) -> str:
        if (
            self.card.set_code != "STA"
            and self.card.promo_types
            and self.card.variations
        ):
            number = self.card.variations[0].number
        else:
            number = self.card.number
        name = (
            self.card.name
            if self.card.layout != "meld"
            else self.card.face_name
        )
        return f"1 {name} ({self.card.set_code}) {number}"

    def pack_sort_key(self) -> tuple[int, bool, int]:
        r = ["mythic", "rare", "uncommon", "common", "special", "bonus"]
        is_common_land = (
            "Land" in self.card.types and self.card.rarity == "common"
        )
        is_basic_land = (
            "Land" in self.card.types and "Basic" in self.card.supertypes
        )
        return (
            is_common_land + is_basic_land,
            self.foil,
            r.index(self.card.rarity),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MtgCard):
            return NotImplemented
        return self.card == other.card

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, MtgCard):
            return NotImplemented
        return self.card < other.card

    def __str__(self) -> str:
        foil_str = " (foil)" if self.foil else ""
        return f"{self.card.name} ({self.card.set_code}){foil_str}"

    def __repr__(self) -> str:
        return f"<boostertutor.models.mtg_card.MtgCard: {str(self)}>"
