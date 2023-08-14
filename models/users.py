from datetime import datetime
from enum import Enum as PythonEnum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.money import Transaction


class Roles(PythonEnum):
    ADMIN = "admin"
    METHODIST = "methodist"
    USER = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    pwd_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[Roles] = mapped_column(Enum(Roles), nullable=False)
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="made_by"
    )  # а оно нужно?

    __table_args__ = (UniqueConstraint("username", name="username_unique"),)

    __mapper_args__ = {"polymorphic_identity": Roles.USER, "polymorphic_on": "role"}

    def __init__(
        self,
        username: str,
        pwd_hash: str,
        role: Optional[Roles],
    ):
        self.username = username
        self.pwd_hash = pwd_hash
        self.role = role if role else Roles.USER


class Admin(User):
    __tablename__ = "admins"

    __mapper_args__ = {"polymorphic_identity": Roles.ADMIN}

    id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)

    def __init__(self, username: str, pwd_hash: str):
        super().__init__(username, pwd_hash, Roles.ADMIN)


class Methodist(User):
    __tablename__ = "methodists"

    __mapper_args__ = {"polymorphic_identity": Roles.METHODIST}

    id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    age_group: Mapped[str] = mapped_column(String(100))

    def __init__(self, username: str, pwd_hash: str, age_group: str):
        super().__init__(username, pwd_hash, Roles.METHODIST)
        self.age_group = age_group


class Token:
    username: str
    exp: int

    def __init__(self, username: str, exp: int):
        self.username = username
        self.exp = exp

    def is_valid(self):
        return datetime.utcnow() < datetime.utcfromtimestamp(self.exp)
