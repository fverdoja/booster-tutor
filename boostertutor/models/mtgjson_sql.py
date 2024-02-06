from functools import total_ordering
from typing import Optional, Union

from sqlalchemy import (
    ForeignKey,
    ForeignKeyConstraint,
    column,
    create_engine,
    select,
    table,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    column_property,
    object_session,
    relationship,
)

SCRYFALL_CARD_BASE_URL = "https://api.scryfall.com/cards"


class Base(DeclarativeBase):
    pass


booster_table = table(
    "setBoosterContentWeights",
    column("booster_content_weight_table.boosterName"),
    column("booster_content_weight_table.setCode"),
)


def parse_str_list(s: str) -> list[str]:
    return s.replace(", ", ",").split(",")


class CardIDs(Base):
    __tablename__ = "cardIdentifiers"

    uuid: Mapped[str] = mapped_column(
        ForeignKey("cards.uuid"), primary_key=True
    )
    scryfall_id: Mapped[str] = mapped_column(name="scryfallId")
    card: Mapped["CardProxy"] = relationship(
        back_populates="identifiers", viewonly=True
    )


@total_ordering
class CardProxy(Base):
    __tablename__ = "cards"

    uuid: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    rarity: Mapped[str]
    number: Mapped[str]
    __types: Mapped[str] = mapped_column(name="types")
    __supertypes: Mapped[str] = mapped_column(name="supertypes")
    layout: Mapped[str]
    face_name: Mapped[Optional[str]] = mapped_column(name="faceName")
    mana_cost: Mapped[Optional[str]] = mapped_column(name="manaCost")
    __colors: Mapped[Optional[str]] = mapped_column(name="colors")
    __promo_types: Mapped[Optional[str]] = mapped_column(name="promoTypes")
    __variations: Mapped[Optional[str]] = mapped_column(name="variations")
    set_code: Mapped[str] = mapped_column(
        ForeignKey("sets.code"), name="setCode"
    )
    set: Mapped["SetProxy"] = relationship(
        back_populates="cards", viewonly=True
    )
    identifiers: Mapped[CardIDs] = relationship(
        back_populates="card", viewonly=True, uselist=False
    )

    @property
    def colors(self) -> list[str]:
        return parse_str_list(self.__colors) if self.__colors else []

    @property
    def types(self) -> list[str]:
        return parse_str_list(self.__types) if self.__types else []

    @property
    def supertypes(self) -> list[str]:
        return parse_str_list(self.__supertypes) if self.__supertypes else []

    @property
    def promo_types(self) -> list[str]:
        return parse_str_list(self.__promo_types) if self.__promo_types else []

    @property
    def variations(self) -> list["CardProxy"]:
        v_list = parse_str_list(self.__variations) if self.__variations else []
        s = object_session(self)
        return (
            list(
                s.scalars(
                    select(CardProxy).filter(CardProxy.uuid.in_(v_list))
                ).all()
            )
            if s and v_list
            else []
        )

    def __repr__(self) -> str:
        return (
            f"Card(name={self.name}, set={self.set_code}, num={self.number})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CardProxy):
            return NotImplemented
        return self.name == other.name

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, CardProxy):
            return NotImplemented
        if self.set != other.set:
            return self.set < other.set

        try:
            mynum = int(self.number)
            othernum = int(other.number)
            return mynum < othernum
        except TypeError:
            pass  # not comparable, no valid integer number

        # try creating a pseudo collectors number
        def _getcol(c: "CardProxy") -> str:
            if c.colors:
                if len(c.colors) > 1:
                    return "M"
                return c.colors[0]
            else:
                if "Land" in c.types:
                    return "L"
                else:
                    return "A"

        col_order = ["W", "U", "B", "R", "G", "M", "A", "L"]

        if col_order.index(_getcol(self)) < col_order.index(_getcol(other)):
            return True

        # go by name
        return self.name < other.name


@total_ordering
class SetProxy(Base):
    __tablename__ = "sets"

    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    release_date: Mapped[str] = mapped_column(name="releaseDate")
    cards: Mapped[list[CardProxy]] = relationship(
        back_populates="set", viewonly=True
    )
    __boosters: Mapped[list["BoosterProxy"]] = relationship(viewonly=True)

    @property
    def boosters(self) -> dict[str, "BoosterProxy"]:
        return {b.name: b for b in self.__boosters}

    def card_by_name(
        self, name: str, case_sensitive: bool = False
    ) -> Union[CardProxy, None]:
        return next(
            (
                c
                for c in self.cards
                if (c.name == name or not case_sensitive)
                and (c.name.lower() == name.lower() or case_sensitive)
            ),
            None,
        )

    def card_by_uuid(self, uuid: str) -> Union[CardProxy, None]:
        return next((c for c in self.cards if c.uuid == uuid), None)

    def __repr__(self) -> str:
        return (
            f"Set(code={self.code}, name={self.name}, "
            f"num_cards={len(self.cards)})"
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SetProxy):
            return NotImplemented
        return self.release_date < other.release_date

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SetProxy):
            return NotImplemented
        return self.name == other.name


class BoosterProxy(Base):
    __tablename__ = booster_table

    name: Mapped[str] = mapped_column(name="boosterName", primary_key=True)
    set_code: Mapped[str] = mapped_column(
        ForeignKey("sets.code"), name="setCode", primary_key=True
    )
    variations: Mapped[list["BoosterVariationProxy"]] = relationship(
        viewonly=True
    )
    sheets: Mapped[list["SheetProxy"]] = relationship(viewonly=True)

    @property
    def total_weight(self) -> int:
        return sum([v.weight for v in self.variations])

    def __repr__(self) -> str:
        return (
            f"Booster(name={self.name}, set_code={self.set_code}, "
            f"variations={self.variations}, total_weight={self.total_weight})"
        )


class SheetCardProxy(Base):
    __tablename__ = "setBoosterSheetCards"
    __table_args__ = (
        ForeignKeyConstraint(
            ["boosterName", "setCode", "sheetName"],
            [
                "setBoosterSheets.boosterName",
                "setBoosterSheets.setCode",
                "setBoosterSheets.sheetName",
            ],
        ),
    )

    _booster_name: Mapped[str] = mapped_column(
        name="boosterName", primary_key=True
    )
    _set_code: Mapped[str] = mapped_column(name="setCode", primary_key=True)
    _sheet_name: Mapped[str] = mapped_column(
        name="sheetName", primary_key=True
    )
    _uuid: Mapped[str] = mapped_column(
        ForeignKey("cards.uuid"), name="cardUuid", primary_key=True
    )
    weight: Mapped[int] = mapped_column(name="cardWeight")
    data: Mapped[CardProxy] = relationship(viewonly=True)

    def __repr__(self) -> str:
        return (
            f"SheetCard(uuid={self._uuid}, name={self.data.name}, "
            f"weight={self.weight})"
        )


class SheetProxy(Base):
    __tablename__ = "setBoosterSheets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["boosterName", "setCode"],
            [BoosterProxy.name, BoosterProxy.set_code],
        ),
    )

    _booster_name: Mapped[str] = mapped_column(
        name="boosterName", primary_key=True
    )
    _set_code: Mapped[str] = mapped_column(name="setCode", primary_key=True)
    name: Mapped[str] = mapped_column(name="sheetName", primary_key=True)
    is_foil: Mapped[bool] = mapped_column(name="sheetIsFoil")
    balance_colors: Mapped[bool] = mapped_column(name="sheetHasBalanceColors")
    cards: Mapped[list[SheetCardProxy]] = relationship(viewonly=True)
    total_weight: Mapped[int] = column_property(
        select(func.sum(SheetCardProxy.weight))
        .where(
            (SheetCardProxy._booster_name == _booster_name)
            & (SheetCardProxy._set_code == _set_code)
            & (SheetCardProxy._sheet_name == name)
        )
        .scalar_subquery()
    )

    def __repr__(self) -> str:
        return (
            f"Sheet(name={self.name}, is_foil={self.is_foil}, "
            f"balance={self.balance_colors}, total_weight={self.total_weight})"
        )


class BoosterVariationProxy(Base):
    __tablename__ = "setBoosterContentWeights"
    __table_args__ = (
        ForeignKeyConstraint(
            ["boosterName", "setCode"],
            [BoosterProxy.name, BoosterProxy.set_code],
        ),
    )

    id: Mapped[int] = mapped_column(name="boosterIndex", primary_key=True)
    _booster_name: Mapped[str] = mapped_column(
        name="boosterName", primary_key=True
    )
    _set_code: Mapped[str] = mapped_column(name="setCode", primary_key=True)
    weight: Mapped[int] = mapped_column(name="boosterWeight")
    content: Mapped[list["BoosterContentProxy"]] = relationship(viewonly=True)

    def __repr__(self) -> str:
        return (
            f"Variation(id={self.id}, weight={self.weight}, "
            f"content={self.content})"
        )


class BoosterContentProxy(Base):
    __tablename__ = "setBoosterContents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["boosterIndex", "boosterName", "setCode"],
            [
                BoosterVariationProxy.id,
                BoosterVariationProxy._booster_name,
                BoosterVariationProxy._set_code,
            ],
        ),
    )

    _variation_id: Mapped[int] = mapped_column(
        name="boosterIndex", primary_key=True
    )
    _booster_name: Mapped[str] = mapped_column(
        name="boosterName", primary_key=True
    )
    _set_code: Mapped[str] = mapped_column(name="setCode", primary_key=True)
    _sheet_name: Mapped[str] = mapped_column(
        ForeignKey("setBoosterSheets.sheetName"),
        name="sheetName",
        primary_key=True,
    )
    num_picks: Mapped[int] = mapped_column(name="sheetPicks")
    sheet: Mapped["SheetProxy"] = relationship(
        viewonly=True,
        primaryjoin=(
            "and_("
            "SheetProxy.name == foreign(BoosterContentProxy._sheet_name), "
            "SheetProxy._booster_name == BoosterContentProxy._booster_name,"
            "SheetProxy._set_code == BoosterContentProxy._set_code"
            ")"
        ),
    )

    def __repr__(self) -> str:
        return f"Content(sheet={self.sheet}, " f"num_picks={self.num_picks})"


class CardDb:
    def __init__(self, database_file: str) -> None:
        self.__engine = create_engine("sqlite:///" + database_file)
        self.__session = Session(self.__engine, autoflush=False)

        sets: list[SetProxy] = list(
            self.__session.scalars(select(SetProxy)).all()
        )
        sets.sort()
        self.sets = {s.code: s for s in sets}

        cards_with_ids = self.__session.execute(
            select(
                CardIDs.uuid, CardIDs.scryfall_id, CardProxy.name, CardProxy
            ).where(CardIDs.uuid == CardProxy.uuid)
        ).all()
        self.cards_by_id: dict[str, CardProxy] = {}
        self.cards_by_scryfall_id: dict[str, CardProxy] = {}
        self.cards_by_name: dict[str, CardProxy] = {}
        for uuid, scryfall_id, name, card in cards_with_ids:
            self.cards_by_id[uuid] = card
            self.cards_by_scryfall_id[scryfall_id] = card
            self.cards_by_name[name] = card

    def get_card_by_name(self, name: str) -> Union[CardProxy, None]:
        return self.cards_by_name.get(name, None)

    def get_card_by_id(self, uuid: str) -> Union[CardProxy, None]:
        return self.cards_by_id.get(uuid, None)

    def get_card_by_scryfall_id(
        self, scryfall_id: str
    ) -> Union[CardProxy, None]:
        return self.cards_by_scryfall_id.get(scryfall_id, None)
