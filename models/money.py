import datetime as dt
from enum import Enum as PythonEnum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.camp import Squad
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

    __mapper_args__ = {"polymorphic_on": "type"}

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
        self.comment = (
            f"+{self.amount}. ({old_balance} -> {self.wallet.current_balance})"
        )
        self.status = TransactionStatus.COMPLETED


class Withdrawal(Transaction):
    __tablename__ = "withdrawals"
    __mapper_args__ = {"polymorphic_identity": TransactionType.WITHDRAWAL}

    id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), primary_key=True)

    def execute(self):
        if self.amount > self.wallet.current_balance:
            self.comment = f"Недостаточно средств. Имеется {self.wallet.current_balance}, необходимо ещё {self.amount - self.wallet.current_balance}."
            self.status = TransactionStatus.FAILED
            raise ValueError(
                f"{self.wallet.squad.number} отряду недостаточно средств. Необходимо ещё {self.amount - self.wallet.current_balance} дружбанов."
            )
        old_balance = self.wallet.current_balance
        self.wallet.current_balance -= self.amount
        self.comment = (
            f"Списано {self.amount}. ({old_balance} -> {self.wallet.current_balance})"
        )
        self.status = TransactionStatus.COMPLETED
