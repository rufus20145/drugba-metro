from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.metro import Station
    from models.money import Wallet


class Squad(Base):
    __tablename__ = "squads"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    stations: Mapped[List["Station"]] = relationship(back_populates="owner")
    wallet: Mapped["Wallet"] = relationship(back_populates="squad")

    def __init__(self, name: str):
        self.name = name
