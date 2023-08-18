import random
from contextlib import contextmanager
from typing import List

import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.exc import SQLAlchemyError

from models import *


class Alchemy:
    def __init__(self, url: str):
        self._engine = sa.create_engine(url)
        Base.metadata.create_all(bind=self._engine)
        self._session_factory = so.sessionmaker(bind=self._engine)

    def get_session(self) -> so.Session:
        return self._session_factory()

    @contextmanager
    def session_scope(self):
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise
        finally:
            session.close()


# тестовые прогоны алхимии
if __name__ == "__main__":
    url = "mysql+pymysql://root:123456789@localhost:3306/test2"

    alchemy = Alchemy(url)
    random_part_of_username = str(random.randint(100000, 999999))

    with alchemy.session_scope() as session:
        line = Line(name="Московская", number="1")
        # station = Station(name="Московский вокзал", line=line, initial_price=100000)
        session.add(line)
        # session.add(station)

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
