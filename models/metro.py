from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.camp import Squad
    from models.metro import Station


class Line(Base):
    __tablename__ = "lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[int] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    number: Mapped[str] = mapped_column(String(5))
    short_name: Mapped[str] = mapped_column(String(100), nullable=True)
    full_line_coef: Mapped[float] = mapped_column(default=1.2)
    stations: Mapped[List["Station"]] = relationship("Station", back_populates="line")

    def __init__(
        self,
        name: str,
        number: str,
        full_line_coef: float = 1.2,
        short_name: Optional[str] = None,
    ):
        self.name = name
        self.number = number
        self.full_line_coef = full_line_coef
        if short_name:
            self.short_name = short_name


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    initial_price: Mapped[int] = mapped_column(Integer)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("squads.id"), nullable=True)
    line: Mapped["Line"] = relationship(back_populates="stations")
    owner: Mapped["Squad"] = relationship(back_populates="stations")

    def __init__(
        self,
        name: str,
        line: Line,
        initial_price: int,
        owner: Optional["Squad"] = None,
    ):
        self.name = name
        self.initial_price = initial_price
        self.line = line
        if owner:
            self.owner = owner
