import enum
from functools import total_ordering
from typing import Optional, Union

from sqlalchemy import (
    ForeignKey,
    ForeignKeyConstraint,
    column,
    create_engine,
    func,
    select,
    table,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    column_property,
    mapped_column,
    object_session,
    relationship,
)

SCRYFALL_CARD_BASE_URL = "https://api.scryfall.com/cards"


class BoosterType(enum.Enum):
    CUBE = "cube"
    DEFAULT = "default"
    DRAFT = "draft"
    DRAFT_ARENA = "arena"
    PLAY = "play"
    PLAY_ARENA = "play-arena"
    ARENA_1 = "arena-1"
    ARENA_2 = "arena-2"
    ARENA_3 = "arena-3"
    ARENA_4 = "arena-4"
    COLLECTOR = "collector"
    JUMPSTART = "jumpstart"
    UNUSED = "unused"


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
    card: Mapped["CardMeta"] = relationship(
        back_populates="identifiers", viewonly=True
    )


@total_ordering
class CardMeta(Base):
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
    __finishes: Mapped[Optional[str]] = mapped_column(name="finishes")
    __promo_types: Mapped[Optional[str]] = mapped_column(name="promoTypes")
    __variations: Mapped[Optional[str]] = mapped_column(name="variations")
    set_code: Mapped[str] = mapped_column(
        ForeignKey("sets.code"), name="setCode"
    )
    set: Mapped["SetMeta"] = relationship(
        back_populates="cards", viewonly=True
    )
    identifiers: Mapped[CardIDs] = relationship(
        back_populates="card", viewonly=True, uselist=False
    )

    @property
    def colors(self) -> list[str]:
        return parse_str_list(self.__colors) if self.__colors else []

    @property
    def finishes(self) -> list[str]:
        return parse_str_list(self.__finishes) if self.__finishes else []

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
    def variations(self) -> list["CardMeta"]:
        v_list = parse_str_list(self.__variations) if self.__variations else []
        s = object_session(self)
        return (
            list(
                s.scalars(
                    select(CardMeta).filter(CardMeta.uuid.in_(v_list))
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
        if not isinstance(other, CardMeta):
            return NotImplemented
        return self.name == other.name

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, CardMeta):
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
        def _getcol(c: "CardMeta") -> str:
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
class SetMeta(Base):
    __tablename__ = "sets"

    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    release_date: Mapped[str] = mapped_column(name="releaseDate")
    cards: Mapped[list[CardMeta]] = relationship(
        back_populates="set", viewonly=True
    )
    __boosters: Mapped[list["BoosterMeta"]] = relationship(viewonly=True)

    @property
    def boosters(self) -> dict[BoosterType, "BoosterMeta"]:
        return {b.name: b for b in self.__boosters}

    def card_by_name(
        self, name: str, case_sensitive: bool = False
    ) -> Union[CardMeta, None]:
        return next(
            (
                c
                for c in self.cards
                if (c.name == name or not case_sensitive)
                and (c.name.lower() == name.lower() or case_sensitive)
            ),
            None,
        )

    def card_by_uuid(self, uuid: str) -> Union[CardMeta, None]:
        return next((c for c in self.cards if c.uuid == uuid), None)

    def __repr__(self) -> str:
        return (
            f"Set(code={self.code}, name={self.name}, "
            f"num_cards={len(self.cards)})"
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SetMeta):
            return NotImplemented
        return self.release_date < other.release_date

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SetMeta):
            return NotImplemented
        return self.name == other.name


class BoosterMeta(Base):
    __tablename__ = booster_table

    name_raw: Mapped[str] = mapped_column("boosterName", primary_key=True)
    set_code: Mapped[str] = mapped_column(
        ForeignKey("sets.code"), name="setCode", primary_key=True
    )
    variations: Mapped[list["BoosterVariationMeta"]] = relationship(
        viewonly=True
    )
    sheets: Mapped[list["SheetMeta"]] = relationship(viewonly=True)

    @property
    def name(self) -> BoosterType:
        try:
            return BoosterType(self.name_raw)
        except ValueError:
            return BoosterType("unused")

    @property
    def total_weight(self) -> int:
        return sum([v.weight for v in self.variations])

    def __repr__(self) -> str:
        return (
            f"Booster(name={self.name}, set_code={self.set_code}, "
            f"variations={self.variations}, total_weight={self.total_weight})"
        )


class SheetCardMeta(Base):
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
    data: Mapped[CardMeta] = relationship(viewonly=True)

    def __repr__(self) -> str:
        return (
            f"SheetCard(uuid={self._uuid}, name={self.data.name}, "
            f"weight={self.weight})"
        )


class SheetMeta(Base):
    __tablename__ = "setBoosterSheets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["boosterName", "setCode"],
            [BoosterMeta.name_raw, BoosterMeta.set_code],
        ),
    )

    _booster_name: Mapped[str] = mapped_column(
        name="boosterName", primary_key=True
    )
    _set_code: Mapped[str] = mapped_column(name="setCode", primary_key=True)
    name: Mapped[str] = mapped_column(name="sheetName", primary_key=True)
    is_foil: Mapped[bool] = mapped_column(name="sheetIsFoil")
    balance_colors: Mapped[bool] = mapped_column(name="sheetHasBalanceColors")
    cards: Mapped[list[SheetCardMeta]] = relationship(viewonly=True)
    total_weight: Mapped[int] = column_property(
        select(func.sum(SheetCardMeta.weight))
        .where(
            (SheetCardMeta._booster_name == _booster_name)
            & (SheetCardMeta._set_code == _set_code)
            & (SheetCardMeta._sheet_name == name)
        )
        .scalar_subquery()
    )

    def __repr__(self) -> str:
        return (
            f"Sheet(name={self.name}, is_foil={self.is_foil}, "
            f"balance={self.balance_colors}, total_weight={self.total_weight})"
        )


class BoosterVariationMeta(Base):
    __tablename__ = "setBoosterContentWeights"
    __table_args__ = (
        ForeignKeyConstraint(
            ["boosterName", "setCode"],
            [BoosterMeta.name_raw, BoosterMeta.set_code],
        ),
    )

    id: Mapped[int] = mapped_column(name="boosterIndex", primary_key=True)
    _booster_name: Mapped[str] = mapped_column(
        name="boosterName", primary_key=True
    )
    _set_code: Mapped[str] = mapped_column(name="setCode", primary_key=True)
    weight: Mapped[int] = mapped_column(name="boosterWeight")
    content: Mapped[list["BoosterContentMeta"]] = relationship(viewonly=True)

    def __repr__(self) -> str:
        return (
            f"Variation(id={self.id}, weight={self.weight}, "
            f"content={self.content})"
        )


class BoosterContentMeta(Base):
    __tablename__ = "setBoosterContents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["boosterIndex", "boosterName", "setCode"],
            [
                BoosterVariationMeta.id,
                BoosterVariationMeta._booster_name,
                BoosterVariationMeta._set_code,
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
    sheet: Mapped["SheetMeta"] = relationship(
        viewonly=True,
        primaryjoin=(
            "and_("
            "SheetMeta.name == foreign(BoosterContentMeta._sheet_name), "
            "SheetMeta._booster_name == BoosterContentMeta._booster_name,"
            "SheetMeta._set_code == BoosterContentMeta._set_code"
            ")"
        ),
    )

    def __repr__(self) -> str:
        return f"Content(sheet={self.sheet}, " f"num_picks={self.num_picks})"


class CardDb:
    def __init__(self, database_file: str) -> None:
        self.__engine = create_engine("sqlite:///" + database_file)
        self.__session = Session(self.__engine, autoflush=False)

        sets: list[SetMeta] = list(
            self.__session.scalars(select(SetMeta)).all()
        )
        sets.sort()
        self.sets = {s.code: s for s in sets}

        cards_with_ids = self.__session.execute(
            select(
                CardIDs.uuid, CardIDs.scryfall_id, CardMeta.name, CardMeta
            ).where(CardIDs.uuid == CardMeta.uuid)
        ).all()
        self.cards_by_id: dict[str, CardMeta] = {}
        self.cards_by_scryfall_id: dict[str, CardMeta] = {}
        self.cards_by_name: dict[str, CardMeta] = {}
        for uuid, scryfall_id, name, card in cards_with_ids:
            self.cards_by_id[uuid] = card
            self.cards_by_scryfall_id[scryfall_id] = card
            self.cards_by_name[name] = card

    def get_card_by_name(self, name: str) -> Union[CardMeta, None]:
        return self.cards_by_name.get(name, None)

    def get_card_by_id(self, uuid: str) -> Union[CardMeta, None]:
        return self.cards_by_id.get(uuid, None)

    def get_card_by_scryfall_id(
        self, scryfall_id: str
    ) -> Union[CardMeta, None]:
        return self.cards_by_scryfall_id.get(scryfall_id, None)
