import random
from datetime import datetime
from enum import Enum as PythonEnum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.camp import AgeGroup, Squad
    from models.money import Transaction


class Roles(PythonEnum):  # уровни доступа
    ADMIN = "Администратор"  # 6
    METHODIST = "Контролёр"  # 5
    COUNSELOR = "Машинист"  # 4
    METRO_CAMPER = "Старший пассажир"  # 3 (специально для 4 отряда)
    CAMPER = "Пассажир"  # 2
    USER = "user"  # 1
    ANONYMOUS = "anonymous"  # 0


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

    def get_access_level(self) -> int:
        if self.role is Roles.ADMIN:
            return 6
        if self.role is Roles.METHODIST:
            return 5
        if self.role is Roles.COUNSELOR:
            return 4
        if self.role is Roles.METRO_CAMPER:
            return 3
        if self.role is Roles.CAMPER:
            return 2
        if self.role is Roles.USER:
            return 1
        return 0


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


class RegisterCode(Base):
    __tablename__ = "register_codes"
    __table_args__ = (UniqueConstraint("code", name="code_unique"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped["User"] = relationship()
    target_squad_id: Mapped[int] = mapped_column(ForeignKey("squads.id"))
    target_squad: Mapped["Squad"] = relationship()
    target_role: Mapped[Roles] = mapped_column(Enum(Roles), nullable=False)

    def __init__(self, created_by: "User", target_squad: "Squad", target_role: Roles):
        self.created_by = created_by
        self.target_squad = target_squad
        self.target_role = target_role
        self.code = self.generate_code()

    def generate_code(self):
        return "".join([str(random.randint(0, 9)) for _ in range(6)])


class Token:
    def __init__(self, username: str, exp: int):
        self.username = username
        self.exp = exp

    def is_valid(self):
        return datetime.utcnow() < datetime.utcfromtimestamp(self.exp)
