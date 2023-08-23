from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.metro import Station
    from models.money import ExchangeRequest, Wallet
    from models.users import Camper, Counselor, Methodist


class AgeGroup(Base):
    __tablename__ = "age_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    squads: Mapped[List["Squad"]] = relationship(back_populates="age_group")
    methodist: Mapped["Methodist"] = relationship(back_populates="age_group")

    def __init__(self, name: str):
        self.name = name


class Squad(Base):
    __tablename__ = "squads"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100))
    age_group_id: Mapped[int] = mapped_column(
        ForeignKey("age_groups.id"), nullable=False
    )
    age_group: Mapped["AgeGroup"] = relationship(back_populates="squads")
    stations: Mapped[List["Station"]] = relationship(back_populates="owner")
    wallet: Mapped["Wallet"] = relationship(back_populates="squad")
    counselors: Mapped[List["Counselor"]] = relationship(back_populates="squad")
    campers: Mapped[List["Camper"]] = relationship(back_populates="squad")
    incoming_exchange_requests: Mapped[List["ExchangeRequest"]] = relationship(
        back_populates="another_squad", foreign_keys="ExchangeRequest.another_squad_id"
    )
    outgoing_exchange_requests: Mapped[List["ExchangeRequest"]] = relationship(
        back_populates="origin_squad", foreign_keys="ExchangeRequest.origin_squad_id"
    )

    def __init__(self, name: str, age_group: "AgeGroup"):
        self.name = name
        self.age_group = age_group

    def get_full_balance(self):
        return self.wallet.current_balance + sum(
            station.initial_price for station in self.stations
        )
