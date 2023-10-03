from functools import total_ordering
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    Session,
)
from sqlalchemy.ext.automap import automap_base
from typing import Optional
from sqlalchemy import (
    ForeignKey,
    ForeignKeyConstraint,
    create_engine,
    column,
    table,
)

Base = automap_base()

booster_table = table(
    "setBoosterContentWeights",
    column("booster_content_weight_table.boosterName"),
    column("booster_content_weight_table.setCode"),
)


@total_ordering
class CardProxy(Base):
    __tablename__ = "cards"

    uuid: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    ascii_name: Mapped[str] = mapped_column(name="asciiName")
    rarity: Mapped[str]
    number: Mapped[str]
    colors: Mapped[Optional[str]]
    set_code: Mapped[str] = mapped_column(
        ForeignKey("sets.code"), name="setCode"
    )
    set: Mapped["SetProxy"] = relationship(
        back_populates="cards", viewonly=True
    )
    types: Mapped[str]

    def __repr__(self) -> str:
        return (
            f"Card(name={self.name}, set_code={self.set_code}, set={self.set})"
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
                return c.colors
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

    @property
    def total_weight(self) -> int:
        return sum([v.weight for v in self.variations])

    def __repr__(self) -> str:
        return (
            f"Booster(name={self.name}, set_code={self.set_code}, "
            f"variations={self.variations}, total_weight={self.total_weight})"
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
    cards: Mapped[list["SheetCardProxy"]] = relationship(viewonly=True)

    @property
    def total_weight(self) -> int:
        return sum([c.weight for c in self.cards])

    def __repr__(self) -> str:
        return (
            f"Sheet(name={self.name}, is_foil={self.is_foil}, "
            f"balance={self.balance_colors}, total_weight={self.total_weight})"
        )


class SheetCardProxy(Base):
    __tablename__ = "setBoosterSheetCards"
    __table_args__ = (
        ForeignKeyConstraint(
            ["boosterName", "setCode", "sheetName"],
            [SheetProxy._booster_name, SheetProxy._set_code, SheetProxy.name],
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


engine = create_engine("sqlite:///data/AllPrintings.sqlite")
Base.prepare(autoload_with=engine)

with Session(engine) as session:
    c1 = session.query(CardProxy).first()
    print(c1)

    znr: SetProxy = (
        session.query(SetProxy).where(SetProxy.code == "ZNR").scalar()
    )
    if znr:
        print(znr.boosters.keys())
        if "default" in znr.boosters:
            print(znr.boosters["default"].variations[0])
    else:
        print("ZNR not found")
