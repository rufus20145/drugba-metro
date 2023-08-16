from datetime import datetime
from enum import Enum as PythonEnum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.camp import AgeGroup, Squad
    from models.money import Transaction


class Roles(PythonEnum):
    ADMIN = "admin"
    METHODIST = "Контролер"
    COUNSELOR = "Машинист"
    CAMPER = "Пассажир"
    METRO_CAMPER = "metro_camper" # специально для 4 отряда, где ребенок отвечает за метро
    USER = "user"


class User(Base):
    __tablename__ = "users"
    __mapper_args__ = {"polymorphic_identity": Roles.USER, "polymorphic_on": "role"}
    __table_args__ = (UniqueConstraint("username", name="username_unique"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    pwd_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[Roles] = mapped_column(Enum(Roles), nullable=False)
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="made_by"
    )  # а оно нужно?

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
    age_group_id: Mapped[int] = mapped_column(
        ForeignKey("age_groups.id"), nullable=False
    )
    age_group: Mapped["AgeGroup"] = relationship(back_populates="methodist")

    def __init__(self, username: str, pwd_hash: str, age_group: "AgeGroup"):
        super().__init__(username, pwd_hash, Roles.METHODIST)
        self.age_group = age_group


class Counselor(User):
    __tablename__ = "counselors"
    __mapper_args__ = {"polymorphic_identity": Roles.COUNSELOR}

    id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    squad_id: Mapped[int] = mapped_column(ForeignKey("squads.id"), nullable=False)
    squad: Mapped["Squad"] = relationship(back_populates="counselors")

    def __init__(self, username: str, pwd_hash: str, squad: "Squad"):
        super().__init__(username, pwd_hash, Roles.COUNSELOR)
        self.squad = squad


class Camper(User):
    __tablename__ = "campers"
    __mapper_args__ = {"polymorphic_identity": Roles.CAMPER}

    id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    squad_id: Mapped[int] = mapped_column(ForeignKey("squads.id"), nullable=False)
    squad: Mapped["Squad"] = relationship(back_populates="campers")

    def __init__(self, username: str, pwd_hash: str, squad: "Squad"):
        super().__init__(username, pwd_hash, Roles.CAMPER)
        self.squad = squad


class MetroCamper(Camper):
    __tablename__ = "metro_campers"
    __mapper_args__ = {"polymorphic_identity": Roles.METRO_CAMPER}

    id: Mapped[int] = mapped_column(ForeignKey("campers.id"), primary_key=True)


class Token:
    def __init__(self, username: str, exp: int):
        self.username = username
        self.exp = exp

    def is_valid(self):
        return datetime.utcnow() < datetime.utcfromtimestamp(self.exp)
