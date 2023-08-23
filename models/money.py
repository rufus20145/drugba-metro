import datetime as dt
from enum import Enum as PythonEnum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.camp import Squad
    from models.metro import Station
    from models.users import User


class Wallet(Base):
    INITIAL_BALANCE = 10000
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(primary_key=True)
    squad_id: Mapped[int] = mapped_column(ForeignKey("squads.id"))
    squad: Mapped["Squad"] = relationship(back_populates="wallet")
    current_balance: Mapped[int] = mapped_column(Integer)
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="wallet")

    def __init__(self, squad: "Squad", initial_balance: Optional[int] = None):
        self.squad = squad
        self.current_balance = initial_balance or Wallet.INITIAL_BALANCE


class TransactionType(PythonEnum):
    DEPOSIT = "Пополнение"
    WITHDRAWAL = "Списание"


class TransactionStatus(PythonEnum):
    CREATED = "created"
    COMPLETED = "completed"
    FAILED = "failed"


class Transaction(Base):
    __tablename__ = "transactions"
    __mapper_args__ = {"polymorphic_on": "type"}

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"))
    wallet: Mapped[Wallet] = relationship(back_populates="transactions")
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    amount: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(100))
    comment: Mapped[str] = mapped_column(String(250))
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus))
    made_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    made_by: Mapped["User"] = relationship(back_populates="transactions")

    def __init__(
        self,
        wallet: Wallet,
        amount: int,
        reason: str,
        made_by: "User",
    ):
        self.wallet = wallet
        self.amount = amount
        self.timestamp = dt.datetime.now()
        self.reason = reason
        self.status = TransactionStatus.CREATED
        self.made_by = made_by

    def execute(self):
        self.status = TransactionStatus.FAILED


class Deposit(Transaction):
    __tablename__ = "deposits"
    __mapper_args__ = {"polymorphic_identity": TransactionType.DEPOSIT}

    id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), primary_key=True)

    def execute(self):
        old_balance = self.wallet.current_balance
        self.wallet.current_balance += self.amount
        self.comment = f"Пополнение на сумму {self.amount}. Баланс: {old_balance} -> {self.wallet.current_balance}"
        self.status = TransactionStatus.COMPLETED


class Withdrawal(Transaction):
    __tablename__ = "withdrawals"
    __mapper_args__ = {"polymorphic_identity": TransactionType.WITHDRAWAL}

    id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), primary_key=True)

    def execute(self):
        if self.amount > self.wallet.current_balance:
            deficit = self.amount - self.wallet.current_balance
            self.comment = f"Списание невозможно. Недостаточно средств. Доступно: {self.wallet.current_balance}, требуется ещё {deficit}."
            self.status = TransactionStatus.FAILED
            raise ValueError(
                f"{self.wallet.squad.number} отряду недостаточно средств. Необходимо ещё {deficit} дружбанов."
            )
        old_balance = self.wallet.current_balance
        self.wallet.current_balance -= self.amount
        self.comment = f"Списание на сумму {self.amount}. Баланс: {old_balance} -> {self.wallet.current_balance}"
        self.status = TransactionStatus.COMPLETED


class RequestType(PythonEnum):
    STATION_PURCHASE = "Покупка станции"
    EXCHANGE = "Сделка"


class RequestStatus(PythonEnum):
    CREATED = "Создана"
    APPROVED = "Выполнена"
    REJECTED = "Отклонена"


class SquadRequest(Base):
    __tablename__ = "requests"
    __mapper_args__ = {"polymorphic_on": "type"}

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.now, nullable=False
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus),
        default=RequestStatus.CREATED,
        nullable=False,
    )
    type: Mapped[RequestType] = mapped_column(Enum(RequestType))
    origin_squad_id: Mapped[int] = mapped_column(ForeignKey("squads.id"))
    origin_squad: Mapped["Squad"] = relationship()

    def __init__(self, origin_squad: "Squad", type: RequestType):
        self.timestamp = dt.datetime.now()
        self.status = RequestStatus.CREATED
        self.origin_squad = origin_squad
        self.type = type


class PurchaseStationRequest(SquadRequest):
    __tablename__ = "purchase_station_requests"
    __mapper_args__ = {"polymorphic_identity": RequestType.STATION_PURCHASE}

    id: Mapped[int] = mapped_column(ForeignKey("requests.id"), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    station: Mapped["Station"] = relationship()

    def __init__(self, origin_squad: "Squad", station: "Station"):
        super().__init__(origin_squad, RequestType.STATION_PURCHASE)
        self.station = station


class ExchangeRequest(SquadRequest):
    __tablename__ = "exchange_requests"
    __mapper_args__ = {"polymorphic_identity": RequestType.EXCHANGE}

    id: Mapped[int] = mapped_column(ForeignKey("requests.id"), primary_key=True)
    another_squad_id: Mapped[int] = mapped_column(
        ForeignKey("squads.id"), nullable=False
    )
    another_squad: Mapped["Squad"] = relationship(
        back_populates="incoming_exchange_requests"
    )
    origin_squad_stations: Mapped[list["OriginExchangeStations"]] = relationship(
        back_populates=""
    )
    another_squad_stations: Mapped[list["AnotherExchangeStations"]] = relationship(
        back_populates=""
    )
    your_squad_withdraw: Mapped[int] = mapped_column(Integer, nullable=True)
    another_squad_withdraw: Mapped[int] = mapped_column(Integer, nullable=True)

    def __init__(
        self,
        squad: "Squad",
        another_squad: "Squad",
        your_squad_station_ids: List[int],
        your_squad_withdraw: int,
        another_squad_station_ids: List[int],
        another_squad_withdraw: int,
    ):
        super().__init__(squad, RequestType.EXCHANGE)
        self.another_squad = another_squad
        self.your_squad_withdraw = your_squad_withdraw
        if your_squad_station_ids:
            self.origin_squad_stations = [
                OriginExchangeStations(station_id=station_id)
                for station_id in your_squad_station_ids
            ]
        if another_squad_station_ids:
            self.another_squad_stations = [
                AnotherExchangeStations(station_id=station_id)
                for station_id in another_squad_station_ids
            ]
        self.another_squad_withdraw = another_squad_withdraw

    def get_your_squad_stations(self) -> str:
        return ", ".join(station.station.name for station in self.origin_squad_stations)

    def get_another_squad_stations(self) -> str:
        return ", ".join(
            station.station.name for station in self.another_squad_stations
        )


class OriginExchangeStations(Base):
    __tablename__ = "exchange_stations_origin"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("exchange_requests.id"))
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    station: Mapped["Station"] = relationship()


class AnotherExchangeStations(Base):
    __tablename__ = "exchange_stations_another"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("exchange_requests.id"))
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    station: Mapped["Station"] = relationship()
