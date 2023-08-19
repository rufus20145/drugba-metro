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
    MONEY_TRANSFER = "Перевод денег"
    STATION_RESELL = "Перепродажа станции"


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
    squad_id: Mapped[int] = mapped_column(ForeignKey("squads.id"), nullable=False)
    squad: Mapped["Squad"] = relationship(back_populates="purchase_requests")

    def __init__(
        self,
        squad: "Squad",
        type: RequestType,
    ):
        self.timestamp = dt.datetime.now()
        self.status = RequestStatus.CREATED
        self.squad = squad
        self.type = type


class PurchaseStationRequest(SquadRequest):
    __tablename__ = "purchase_station_requests"
    __mapper_args__ = {"polymorphic_identity": RequestType.STATION_PURCHASE}

    id: Mapped[int] = mapped_column(ForeignKey("requests.id"), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    station: Mapped["Station"] = relationship()

    def __init__(self, squad: "Squad", station: "Station"):
        super().__init__(squad, RequestType.STATION_PURCHASE)
        self.station = station
