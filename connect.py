from typing import List, Optional
import sqlalchemy as sa
import sqlalchemy.orm as so

Base = so.declarative_base()


class Line(Base):
    __tablename__ = "lines"

    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    order_number: so.Mapped[int] = so.mapped_column(sa.Integer)
    number: so.Mapped[str] = so.mapped_column(sa.String(5))
    name: so.Mapped[str] = so.mapped_column(sa.String(100))
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


class Alchemy:
    def __init__(self, url: str):
        self._engine = sa.create_engine(url)
        Base.metadata.create_all(bind=self._engine)
        self._session_factory = so.sessionmaker(bind=self._engine)

    def get_session(self) -> so.Session:
        return self._session_factory()

    def get_line_by_number(self, number: str, session: so.Session) -> "Line":
        query = sa.select(Line).filter_by(number=number)
        result = session.scalars(query).one_or_none()
        return result

    def get_all_lines(self, session: so.Session) -> List["Line"]:
        query = sa.select(Line)
        result = session.scalars(query).all()
        return result


if __name__ == "__main__":
    url = "mysql+pymysql://root:123456789@localhost:3306/metro"

    alchemy = Alchemy(url)

    with alchemy.get_session() as session:
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
        #         session.commit()

        # установка коэффициентов для линий
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
        #     session.commit()

        # установка цен для станций
        stations_inside_circle = [""]
        stations_on_circle = [
            "Киевская",
            "Краснопресненская",
            "Белорусская",
            "Новослободская",
            "Проспект Мира",
            "Комсомольская",
            "Курская",
            "Таганская",
            "Павелецкая",
            "Добрынинская",
            "Октябрьская",
            "Парк культуры",
        ]
        print(f"{len(stations_on_circle)} станций в списке stations_inside_circle")

        query = sa.select(Station)
        result = session.scalars(query).all()
        for station in result:
            if station.name in stations_on_circle and station.line.name == "Кольцевая":
                station.initial_price = 100_000
                print(station.name)

                session.merge(station)
                session.commit()