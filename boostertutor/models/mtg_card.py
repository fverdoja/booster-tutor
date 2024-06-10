from datetime import timedelta
from typing import Literal, Optional

import imageio.v3 as iio
import numpy as np
from aiohttp_client_cache.backends.sqlite import SQLiteBackend
from aiohttp_client_cache.session import CachedSession

from boostertutor.models.mtgjson_sql import CardProxy
from boostertutor.utils.utils import foil_layer

SCRYFALL_CARD_BASE_URL = "https://api.scryfall.com/cards"
CardImageSize = Literal["large", "normal", "small", "png", "border_crop"]

cache = SQLiteBackend(
    cache_name=".aiohttp_cache/scryfall.sqlite",
    urls_expire_after={
        f"{SCRYFALL_CARD_BASE_URL}/*?format=image*": timedelta(days=30),
        f"{SCRYFALL_CARD_BASE_URL}/*": timedelta(days=1),
    },
)


class MtgCard:
    """A Magic: The Gathering card representation.

    This class encapsulates all the details and functionalities of an
    individual MtG card. This class wraps a CardProxy instance, which
    represents a specific card prototype and contains all card data (e.g.,
    name, cost, oracle text).

    Attributes:
        card: A CardProxy instance containing all the card's data.
        foil: A boolean indicating whether the card is foil.
    """

    def __init__(self, card: CardProxy, foil: bool = False) -> None:
        """Initializes the MtgCard instance.

        Args:
            card (CardProxy): An instance of CardProxy that represents a
            specific card.
            foil (bool, optional): A boolean value that indicates if the card
            is foil. Defaults to False
        """
        self.card = card
        self.foil = foil

    def mana(self) -> list[str]:
        """Determines the color(s) of the card.

        The method will extract the colors based on the mana cost of the
        card. It handles both regular mana costs and hybrid mana (represented
        as fractions).

        Returns:
            list[str]: A list of strings representing the colors of mana in the
            cost, if any. The color codes follow the convention: "W" for White,
            "U" for Blue, "B" for Black, "R" for Red, and "G" for Green.
        """
        colors = ["W", "U", "B", "R", "G"]

        if self.card.mana_cost:
            cost = self.card.mana_cost.lstrip("{").rstrip("}").split("}{")
            mana = [c for c in colors if c in cost]
            if not mana:
                hybrid = []
                for symbol in cost:
                    if "/" in symbol:
                        hybrid += symbol.split("/")
                hybrid_colors = [c for c in colors if c in hybrid]
                if len(hybrid_colors) == 2:
                    mana = [hybrid_colors[0] + hybrid_colors[1]]
                else:
                    mana = hybrid_colors
        else:
            mana = self.card.colors
        return mana

    async def get_price(
        self,
        currency: Literal["eur", "usd"],
        eur_usd_rate: Optional[float] = None,
    ) -> Optional[float]:
        """Retrieves the price of the card in the specified currency.

        This method makes an async request to Scryfall to fetch the price.
        If the price is not available in the specified currency but is
        available in an alternative currency, it converts the price to the
        specified currency using the provided exchange rate.

        Args:
            currency (str): The currency in which to return the price. Must be
            'eur' or 'usd'.
            eur_usd_rate (float, optional): The conversion rate from EUR to USD
            used if conversion is required. If None (Default) no currency
            conversion is performed.

        Returns:
            float: The price of the card in the specified currency, or None if
            the price could not be retrieved.

        Raises:
            ValueError: If the specified currency is not 'eur' or 'usd'.
        """
        currencies = ("eur", "usd")
        if currency == "eur":
            pref_currency, alt_currency = currencies
        elif currency == "usd":
            alt_currency, pref_currency = currencies
        else:
            raise ValueError("Currency is not 'eur' or 'usd'")
        if self.foil:
            pref_currency += "_foil"
            alt_currency += "_foil"

        scry_id = self.card.identifiers.scryfall_id
        card_url = f"{SCRYFALL_CARD_BASE_URL}/{scry_id}"

        async with CachedSession(cache=cache) as session:
            async with session.get(card_url) as resp:
                resp.raise_for_status()
                card = await resp.json()

        price = card["prices"][pref_currency]
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
        self, size: CardImageSize = "normal", foil: Optional[bool] = None
    ) -> np.ndarray:
        """Retrieves the image of the card in the given size.

        This method sends an async get request to Scryfall to fetch the
        image. If the card is foil (or if the optional foil parameter is True),
        it applies a foil layer to the image.

        Args:
            size (str, optional): The desired size of the image. This must be
            one of the following: 'large', 'normal', 'small', 'png',
            'border_crop'. Defaults to 'normal'.
            foil (bool, optional): Whether to apply the foil layer. If None
            (Default), the instance's foil attribute is used.

        Returns:
            np.ndarray: The card's image as a numpy array.

        Raises:
            ValueError: If the specified size is not one of the acceptable
            values.
        """
        sizes = ["large", "normal", "small", "png", "border_crop"]
        if size not in sizes:
            raise ValueError(
                "The specified size is not one of the acceptable values."
            )

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

        im: np.ndarray = iio.imread(resp_bytes)

        if foil:
            foil_im = foil_layer(size=im.shape[0:2])
            im[..., 0:3] = (im[..., 0:3] * 0.7 + foil_im * 0.3).astype("uint8")

        return im

    def json(self) -> dict:
        """Converts the card data to JSON.

        This method generates a dictionary representation of the card which can
        easily be converted into JSON and is compatible with SealedDeck.Tech
        APIs. Depending on the layout of the card (normal or meld), it uses
        either the card name or the front face name as the name.

        Returns:
            dict: A dictionary with keys 'name', 'set', and 'count',
            representing the card's name, set code, and count respectively.
        """
        name = (
            self.card.name
            if self.card.layout != "meld"
            else self.card.face_name
        )
        return {"name": name, "set": self.card.set.code, "count": 1}

    def arena_format(self) -> str:
        """Returns the card information into MTG Arena format"""
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
        """Generates a sorting key for ordering cards in a pack.

        The sorting key is a tuple containing three values to sort by:
        1. Whether or not the card is a common or basic land (1 if true,
        0 if false).
        2. Whether or not the card is foil.
        3. An index for the card rarity (from most to least rare).

        Returns:
            tuple[int, bool, int]: A tuple to be used as key for sorting.
        """
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


async def clear_expired_card_info_cache() -> None:
    async with CachedSession(cache=cache) as session:
        await session.delete_expired_responses()
