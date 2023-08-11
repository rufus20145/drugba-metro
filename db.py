import datetime as dt
import hashlib
import random
from typing import List, Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.dialects.mysql import INTEGER


class Base(so.DeclarativeBase):
    pass


class Line(Base):
    __tablename__ = "lines"

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    order_number: so.Mapped[int] = so.mapped_column(sa.Integer)
    number: so.Mapped[str] = so.mapped_column(sa.String(5))
    name: so.Mapped[str] = so.mapped_column(sa.String(100))
    short_name: so.Mapped[str] = so.mapped_column(sa.String(100))
    full_line_coef: so.Mapped[float] = so.mapped_column()
    stations: so.Mapped[List["Station"]] = so.relationship(back_populates="line")

    def __init__(self, name: str, number: str, full_line_coef: float):
        self.name = name
        self.number = number
        self.full_line_coef = full_line_coef


class Station(Base):
    __tablename__ = "stations"

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(100))
    initial_price: so.Mapped[int] = so.mapped_column(sa.Integer)
    line_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("lines.id"))
    owner_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("squads.id"))
    line: so.Mapped["Line"] = so.relationship(back_populates="stations")
    owner: so.Mapped["Squad"] = so.relationship(back_populates="stations")

    def __init__(self, name: str, line_id: int, owner_id: Optional[int] = None):
        self.name = name
        self.line_id = line_id
        self.owner_id = owner_id


class Squad(Base):
    __tablename__ = "squads"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(100))
    stations: so.Mapped[List["Station"]] = so.relationship(back_populates="owner")
    wallet: so.Mapped["Wallet"] = so.relationship(back_populates="squad")


class Wallet(Base):
    __tablename__ = "wallets"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    squad_id: so.Mapped[int] = so.mapped_column(
        INTEGER(unsigned=True), sa.ForeignKey("squads.id")
    )
    squad: so.Mapped["Squad"] = so.relationship(back_populates="wallet")
    balance: so.Mapped[int] = so.mapped_column(sa.Integer)
    transactions: so.Mapped[List["Transaction"]] = so.relationship()

    def __init__(self, squad_id: int):
        self.squad_id = squad_id
        self.balance = 10000


class Transaction(Base):
    __tablename__ = "transactions"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    date: so.Mapped[dt.datetime] = so.mapped_column(sa.DateTime)
    wallet_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("wallets.id"))
    amount: so.Mapped[int] = so.mapped_column(sa.Integer)
    made_by_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"))
    wallet: so.Mapped["Wallet"] = so.relationship(back_populates="transactions")


class User(Base):
    __tablename__ = "users"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(100), nullable=False)
    pwd_hash: so.Mapped[str] = so.mapped_column(sa.String(64), nullable=False)
    role: so.Mapped[str] = so.mapped_column(sa.String(100), nullable=False)

    __table_args__ = (
        # sa.CheckConstraint("username ~ '^[a-zA-Z0-9]{5,}$'", name="username_check"),
        sa.UniqueConstraint("username", name="username_unique"),
    )

    __mapper_args__ = {"polymorphic_identity": "user", "polymorphic_on": "role"}

    def __init__(
        self,
        username: str,
        pwd_hash: str,
        role: Optional[str],
    ):
        self.username = username
        self.pwd_hash = pwd_hash
        self.role = role if role else "User"


class Admin(User):
    __tablename__ = "admins"

    __mapper_args__ = {"polymorphic_identity": "admin"}

    id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"), primary_key=True)

    def __init__(self, username: str, pwd_hash: str):
        super().__init__(username, pwd_hash, "admin")


class Methodist(User):
    __tablename__ = "methodists"

    __mapper_args__ = {"polymorphic_identity": "methodist"}

    id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    age_group: so.Mapped[str] = so.mapped_column(sa.String(100))

    def __init__(self, username: str, pwd_hash: str, age_group: str):
        super().__init__(username, pwd_hash, "methodist")
        self.age_group = age_group


class Token(Base):
    __tablename__ = "tokens"

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"))
    token: so.Mapped[str] = so.mapped_column(sa.String(64), nullable=False)
    created_at: so.Mapped[dt.datetime] = so.mapped_column(sa.DateTime)
    valid_until: so.Mapped[dt.datetime] = so.mapped_column(sa.DateTime)

    def __init__(self, user: User):
        self.user_id = user.id
        self.token = self._hash(user.username + user.pwd_hash + str(dt.datetime.now()))
        self.created_at = dt.datetime.now()
        self.valid_until = self.created_at + dt.timedelta(days=14)

    def is_valid(self) -> bool:
        return self.valid_until > dt.datetime.now()

    def update(self, session: so.Session) -> None:
        query = sa.select(User).filter_by(id=self.user_id)
        user = session.scalars(query).one_or_none()
        self.token = self._hash(user.username + user.pwd_hash + str(dt.datetime.now()))
        self.created_at = dt.datetime.now()
        self.valid_until = self.created_at + dt.timedelta(days=14)
        session.merge(self)
        session.commit()

    def _hash(self, string: str) -> str:
        return hashlib.sha256(string.encode("utf-8")).hexdigest()


class LogMessage(Base):
    __tablename__ = "log_messages"

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(150))
    message: so.Mapped[str] = so.mapped_column(sa.String(1000))
    datetime: so.Mapped[dt.datetime] = so.mapped_column(sa.DateTime)

    def __init__(self, username: str, message: str):
        self.username = username
        self.message = message
        self.datetime = dt.datetime.now()


class Alchemy:
    def __init__(self, url: str):
        self._engine = sa.create_engine(url)
        Base.metadata.create_all(bind=self._engine)
        self._session_factory = so.sessionmaker(bind=self._engine)

    def get_session(self) -> so.Session:
        return self._session_factory()

    def get_line_by_number(self, number: str, session: so.Session) -> "Line":
        query = sa.select(Line).filter_by(number=number)
        line = session.scalars(query).one_or_none()
        return line

    def get_squad_by_number(self, number: str, session: so.Session) -> "Squad":
        query = sa.select(Squad).filter_by(name=number)
        squad = session.scalars(query).one_or_none()
        return squad

    def change_station_owner(
        self, station_id: int, new_owner_id: int, session: so.Session
    ) -> int:
        if new_owner_id == -1:
            new_owner_id = None

        query = sa.select(Station).where(Station.id == station_id)
        old_owner_id = session.scalars(query).one_or_none().owner_id
        query = (
            sa.update(Station)
            .where(Station.id == station_id)
            .values(owner_id=new_owner_id)
        )
        session.execute(query)
        session.commit()
        return old_owner_id

    def get_station_name(self, station_id: int, session: so.Session) -> str:
        query = sa.select(Station).where(Station.id == station_id)
        station = session.scalars(query).one_or_none()
        return station.name

    def get_station_price(self, station_id: int, session: so.Session) -> int:
        query = sa.select(Station).where(Station.id == station_id)
        station = session.scalars(query).one_or_none()
        return station.initial_price

    def get_all_lines(self, session: so.Session) -> List["Line"]:
        query = sa.select(Line)
        lines = session.scalars(query).all()
        return lines

    def get_all_stations(self, session: so.Session) -> List["Station"]:
        query = sa.select(Station)
        stations = session.scalars(query).all()
        return stations

    def get_all_squads(self, session: so.Session) -> List["Squad"]:
        query = sa.select(Squad)
        squads = session.scalars(query).all()
        return squads

    def get_user_by_username(self, username: str, session: so.Session) -> "User":
        query = sa.select(User).filter_by(username=username)
        user = session.scalars(query).one_or_none()
        return user

    def get_user_by_token(self, token: str) -> "User":
        query = sa.select(Token).filter_by(token=token)
        token = self.get_session().scalars(query).one_or_none()
        if token is None:
            return None
        query = sa.select(User).filter_by(id=token.user_id)
        user = self.get_session().scalars(query).one_or_none()
        return user

    def get_or_generate_token(self, user: User) -> str:
        with self.get_session() as session:
            query = sa.select(Token).filter_by(user_id=user.id)
            token: Token = session.scalars(query).one_or_none()
            if token:
                token.update(session)
            else:
                token = Token(user)
                session.add(token)
                session.commit()
            return token.token

    def add_balance(self, squad_number: int, amount: int, session: so.Session) -> int:
        query = sa.Select(Squad).where(Squad.name == str(squad_number))
        squad: Squad = session.scalars(query).one_or_none()
        old_balance = squad.wallet.balance
        squad.wallet.balance += amount
        session.merge(squad)
        session.commit()
        return old_balance

    def get_bought_stations(self, session: so.Session) -> List["Station"]:
        query = sa.select(Station).where(Station.owner_id != None)
        stations = session.scalars(query).all()
        return stations


# тестовые прогоны алхимии
if __name__ == "__main__":
    url = "mysql+pymysql://root:123456789@localhost:3306/metro"

    alchemy = Alchemy(url)
    random_part_of_username = str(random.randint(100000, 999999))

    with alchemy.get_session() as session:
        query = sa.select(Squad)
        squads = session.scalars(query).all()
        for squad in squads:
            wallet = Wallet(squad.id)
            session.add(wallet)
            session.commit()

        # обновление цен станций
        # query = sa.select(Station)
        # all_stations = session.scalars(query).all()
        # for station in all_stations:
        #     match station.initial_price:
        #         case 60000:
        #             station.initial_price = 100000
        #         case 70000:
        #             station.initial_price = 140000
        #         case 100000:
        #             station.initial_price = 170000
        #         case 140000:
        #             station.initial_price = 220000
        #     session.merge(station)

        # вывод списка линий по в правильном порядке
        # query = sa.select(Line).order_by(Line.order_number)
        # result = session.scalars(query).all()
        # sum = 0
        # for line in result:
        #     sum += len(line.stations)
        #     print(
        #         "{0:4} {1:60} {2}".format(
        #             line.number, line.name, str(len(line.stations))
        #         )
        #     )
        # print(sum)

        # удаление лишних переносов строк
        # query2 = sa.select(Station)  # выбор линии
        # result2 = session.scalars(query2).all()
        # for station in result2:
        #     # remove \n in the end of station.name and update in db
        #     if station.name.endswith("\n"):
        #         print(f"Удаляем перенос у станции: {station.name}")
        #         input("Press any key to continue...")
        #         station.name = station.name[:-1]
        #         session.merge(station)

        # вычисление коэффициентов для линий
        # query = sa.select(Line).order_by(Line.order_number)
        # result = session.scalars(query).all()
        # for line in result:
        #     line.full_line_coef = round(len(line.stations) / 7 + 0.2, 1)
        #     print(
        #         "{0:4} {1:60} {2:4} {3:4}".format(
        #             line.number, line.name, len(line.stations), line.full_line_coef
        #         )
        #     )
        #     session.merge(line)

        session.commit()
