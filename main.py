import os
from datetime import datetime, timedelta
from typing import Annotated, Any

import sqlalchemy as sa
import sqlalchemy.orm as so
import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext

from models.base import Base
from models.camp import Squad
from models.metro import Line, Station
from models.money import Deposit, Transaction, TransactionStatus, Wallet, Withdrawal
from models.users import Camper, Counselor, RegisterCode, Roles, Token, User

url = os.getenv("DATABASE_URL")
if not url:
    raise RuntimeError("DATABASE_URL is not set")
engine = sa.create_engine(url)
Base.metadata.create_all(bind=engine)
SessionLocal = so.sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()  # docs_url=None, redoc_url=None, openapi_url=None
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=8)


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30


def create_access_token(username: str):
    data: dict[str, Any] = {"username": username}

    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    data.update({"exp": expire})
    encoded_jwt = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def parse_token(token: str) -> Token | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        tkn = Token(**payload)
        return tkn
    except JWTError as e:
        print(e)
        return None


def get_stations_str(number_of_stations: int) -> str:
    match number_of_stations % 10:
        case 0 | 1:
            return str(number_of_stations) + " станция"
        case 2 | 3 | 4:
            return str(number_of_stations) + " станции"
        case 5 | 6 | 7 | 8 | 9:
            return str(number_of_stations) + " станций"
        case _:
            return "неправильный остаток от деления на 10"


@app.get(path="/", response_class=HTMLResponse)
def get_root_page(request: Request, db: so.Session = Depends(get_db)):
    lines_q = sa.select(Line).order_by(Line.order_number)
    lines = list(db.scalars(lines_q))

    squads_q = sa.select(Squad)
    squads = list(db.scalars(squads_q))

    return templates.TemplateResponse(
        "index.html", {"request": request, "lines": lines, "squads": squads}
    )


@app.get("/bought-stations", response_class=HTMLResponse)
def get_bought_stations_page(request: Request, db: so.Session = Depends(get_db)):
    bought_stations_q = sa.select(Station).where(Station.owner_id != None)
    bought_stations = list(db.scalars(bought_stations_q))
    return templates.TemplateResponse(
        "bought-stations.html",
        {"request": request, "bought_stations": bought_stations},
    )


@app.get(path="/squad/{number}", response_class=HTMLResponse)
def get_squad_info(request: Request, number: int, db: so.Session = Depends(get_db)):
    squad_q = sa.select(Squad).filter_by(number=number)
    squad = db.scalars(squad_q).one_or_none()
    if not squad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Состав с таким номером не найден",
        )
    return templates.TemplateResponse(
        "squad.html", {"request": request, "squad": squad}
    )


@app.get(path="/line/{number}", response_class=HTMLResponse)
def get_line_info(request: Request, number: str, db: so.Session = Depends(get_db)):
    line_q = sa.select(Line).filter_by(number=number)
    line = db.scalars(line_q).one_or_none()
    if not line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Линия с таким номером не найдена",
        )
    return templates.TemplateResponse("line.html", {"request": request, "line": line})


@app.get(path="/login", response_class=HTMLResponse)
def get_auth_page(request: Request, db: so.Session = Depends(get_db)):
    token_str = request.cookies.get("token")
    if token_str:
        token = parse_token(token_str)
        if token and token.is_valid():
            user_q = sa.select(User).filter_by(username=token.username)
            user = db.scalars(user_q).one_or_none()
            if user:
                return RedirectResponse("/profile", status_code=status.HTTP_302_FOUND)
    response = templates.TemplateResponse("login.html", {"request": request})
    response.delete_cookie("token")
    return response


@app.post(path="/login", response_class=JSONResponse)
def login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: so.Session = Depends(get_db),
):
    token_str = request.cookies.get("token")
    if token_str:
        token = parse_token(token_str)
        if token and token.is_valid():
            user_q = sa.select(User).filter_by(username=token.username)
            user = db.scalars(user_q).one_or_none()
            if user:
                return RedirectResponse("/profile", status_code=status.HTTP_302_FOUND)

    user_q = sa.select(User).filter_by(username=username)
    user = db.scalars(user_q).one_or_none()
    if not user:
        pwd_context.dummy_verify()
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": "Неверный логин или пароль"},
        )
    if not pwd_context.verify(password, user.pwd_hash):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": "Неверный логин или пароль"},
        )
    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Аутентификация прошла успешно"},
    )
    token = create_access_token(user.username)
    response.set_cookie("token", token, expires=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)
    return response


@app.get(path="/register", response_class=HTMLResponse)
def get_register_page(request: Request, db: so.Session = Depends(get_db)):
    token_str = request.cookies.get("token")
    if token_str:
        token = parse_token(token_str)
        if token and token.is_valid():
            user_q = sa.select(User).filter_by(username=token.username)
            user = db.scalars(user_q).one_or_none()
            if user:
                return RedirectResponse("/profile", status_code=status.HTTP_302_FOUND)

        roles = [Roles.COUNSELOR, Roles.CAMPER]
        squads_q = sa.select(Squad)
        squads = list(db.scalars(squads_q))
        response = templates.TemplateResponse(
            "register.html", {"request": request, "roles": roles, "squads": squads}
        )
        response.delete_cookie("token")
        return response


@app.post(path="/register", response_class=JSONResponse)
def register(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    code: Annotated[int, Form()],
    role_str: Annotated[str, Form()],
    squad_number: Annotated[int, Form()],
    db: so.Session = Depends(get_db),
):
    token_str = request.cookies.get("token")
    if token_str:
        token = parse_token(token_str)
        if token and token.is_valid():
            user_q = sa.select(User).filter_by(username=token.username)
            user = db.scalars(user_q).one_or_none()
            if user:
                return RedirectResponse("/profile", status_code=status.HTTP_302_FOUND)

    role = Roles[role_str]

    user_q = sa.select(User).filter_by(username=username)
    user = db.scalars(user_q).one_or_none()
    if user:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Пользователь с таким логином уже существует"},
        )

    squad_q = sa.select(Squad).filter_by(number=squad_number)
    squad = db.scalars(squad_q).one_or_none()
    if not squad:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Состава с таким номером не найдено"},
        )

    reg_code_q = sa.select(RegisterCode).filter_by(code=code)
    reg_code = db.scalars(reg_code_q).one_or_none()

    if not reg_code:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Код не найден"},
        )

    match role:
        case Roles.COUNSELOR:
            if reg_code.target_role != Roles.COUNSELOR:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message": "Данный код не предназначен для регистрации с данной ролью"
                    },
                )
            if reg_code.target_squad.number != squad.number:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"message": "Данный код предназначен для другого состава"},
                )
            new_user = Counselor(username, pwd_context.hash(password), squad)
        case Roles.CAMPER:
            if reg_code.target_role != Roles.CAMPER:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "message": "Данный код не предназначен для регистрации с данной ролью"
                    },
                )
            if reg_code.target_squad.number != squad.number:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"message": "Данный код предназначен для другого состава"},
                )
            new_user = Camper(username, pwd_context.hash(password), squad)
        case _:
            return JSONResponse(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                content={"message": "Неизвестная роль."},
            )
    db.add(new_user)
    db.commit()
    response = JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"message": "Регистрация прошла успешно"},
    )
    token = create_access_token(username)
    response.set_cookie("token", token, expires=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)
    return response


@app.get(path="/profile", response_class=HTMLResponse)
def get_profile_page(request: Request, db: so.Session = Depends(get_db)):
    login_redirect = RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    token_str = request.cookies.get("token")
    if not token_str:
        return login_redirect
    token = parse_token(token_str)
    if not token:
        return login_redirect
    if not token.is_valid():
        return login_redirect

    user_q = sa.select(User).filter_by(username=token.username)
    user = db.scalars(user_q).one_or_none()
    if not user:
        return login_redirect

    match user.role:
        case Roles.ADMIN | Roles.METHODIST:
            return templates.TemplateResponse(
                "/profile/admin.html", {"request": request, "user": user}
            )
        case Roles.COUNSELOR:
            user_2: Counselor = user  # type: ignore
            stations_str: str = get_stations_str(len(user_2.squad.stations))

            free_stations_q = sa.select(Station).filter_by(owner_id=None)
            free_stations = list(db.scalars(free_stations_q))

            transactions_q = sa.select(Transaction).filter_by(
                wallet_id=user_2.squad.wallet.id, status=TransactionStatus.COMPLETED
            )
            transactions = list(db.scalars(transactions_q))

            return templates.TemplateResponse(
                "/profile/counselor.html",
                {
                    "request": request,
                    "user": user,
                    "stations_str": stations_str,
                    "free_stations": free_stations,
                    "transactions": transactions,
                },
            )
        case Roles.CAMPER:
            user_2: Camper = user  # type: ignore
            stations_str: str = get_stations_str(len(user_2.squad.stations))
            return templates.TemplateResponse(
                "/profile/camper.html",
                {"request": request, "user": user, "stations_str": stations_str},
            )
        case _:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="У пользователя неизвестная роль",
            )


@app.get(path="/logout", response_class=RedirectResponse)
def logout():
    response = RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("token")
    return response


@app.post(path="/buy-station", response_class=JSONResponse)
def buy_station(
    request: Request,
    station_id: Annotated[int, Form()],
    db: so.Session = Depends(get_db),
):
    no_permission = JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN, content={"message": "No permission"}
    )
    token_str = request.cookies.get("token")
    if not token_str:
        return no_permission
    token = parse_token(token_str)
    if not token:
        return no_permission
    if not token.is_valid():
        return no_permission
    user_q = sa.select(User).filter_by(username=token.username)
    user = db.scalars(user_q).one_or_none()
    if not user:
        return no_permission

    if user.role != Roles.COUNSELOR:
        return no_permission
    user_2: Counselor = user  # type: ignore
    station_q = sa.select(Station).filter_by(id=station_id)
    station = db.scalars(station_q).one_or_none()
    if not station:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Станция не найдена"},
        )
    if station.owner_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": f"Станция уже куплена. Текущий владелец: {station.owner.number} состав"
            },
        )
    try:
        withdrawal = Withdrawal(
            wallet=user_2.squad.wallet,
            amount=station.initial_price,
            reason=f"Покупка станции {station.name}",
            made_by=user_2,
        )
        db.add(withdrawal)
        withdrawal.execute()
        station.owner_id = user_2.squad_id
        db.merge(station)
        db.commit()
        formatted_balance = "{:,}".format(user_2.squad.wallet.current_balance).replace(
            ",", " "
        )
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": f"Станция {station.name} успешно куплена.",
                "new_balance": formatted_balance,
            },
        )
    except ValueError as e:
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"message": str(e)}
        )


@app.post(path="/get-code", response_class=JSONResponse)
def get_code(
    request: Request,
    squad_id: Annotated[int, Form()],
    db: so.Session = Depends(get_db),
):
    no_permission = JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN, content={"message": "No permission"}
    )
    token_str = request.cookies.get("token")
    if not token_str:
        return no_permission
    token = parse_token(token_str)
    if not token:
        return no_permission
    if not token.is_valid():
        return no_permission

    user_q = sa.select(User).filter_by(username=token.username)
    user = db.scalars(user_q).one_or_none()
    if not user:
        return no_permission

    target_squad_q = sa.select(Squad).filter_by(id=squad_id)
    target_squad = db.scalars(target_squad_q).one_or_none()
    if not target_squad:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Состава с таким номером не найдено"},
        )

    if user.role == Roles.ADMIN or user.role == Roles.METHODIST:
        target_role = Roles.COUNSELOR
    else:
        target_role = Roles.CAMPER

    reg_code_q = sa.select(RegisterCode).filter_by(
        target_squad_id=squad_id, target_role=target_role
    )
    reg_code = db.scalars(reg_code_q).one_or_none()
    if not reg_code:
        reg_code = RegisterCode(user, target_squad, target_role=target_role)
        db.add(reg_code)
        db.commit()
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "message": f"Код для регистрации в {target_squad.number} составе — {reg_code.code}."
        },
    )


@app.post(path="/admin/add-balance", response_class=JSONResponse)
def add_balance(
    request: Request,
    squad_id: Annotated[int, Form()],
    type: Annotated[str, Form()],
    amount: Annotated[int, Form()],
    reason: Annotated[str, Form()],
    db: so.Session = Depends(get_db),
):
    no_permission = JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN, content={"message": "No permission"}
    )
    token_str = request.cookies.get("token")
    if not token_str:
        return no_permission

    token = parse_token(token_str)
    if not token:
        return no_permission

    if not token.is_valid():
        return no_permission

    user_q = sa.select(User).filter_by(username=token.username)
    user = db.scalars(user_q).one_or_none()
    if not user:
        return no_permission
    if user.role != Roles.ADMIN and user.role != Roles.METHODIST:
        return no_permission

    wallet_q = sa.select(Wallet).filter_by(squad_id=squad_id)
    wallet = db.scalars(wallet_q).one_or_none()
    if not wallet:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Состав не найден"},
        )
    old_balance = wallet.current_balance
    try:
        if type == "deposit":
            deposit = Deposit(wallet=wallet, amount=amount, reason=reason, made_by=user)
            db.add(deposit)
            deposit.execute()
        elif type == "withdraw":
            withdrawal = Withdrawal(
                wallet=wallet, amount=amount, reason=reason, made_by=user
            )
            db.add(withdrawal)
            withdrawal.execute()

        db.commit()
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": f"Баланс {squad_id} отряда успешно обновлен ({old_balance} -> {wallet.current_balance})"
            },
        )
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"message": str(e)}
        )


# ======================================================================================
@app.exception_handler(HTTPException)
@app.exception_handler(404)
def page_not_found(request: Request, exc: HTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "info": exc.detail},
            status_code=exc.status_code,
        )
    return templates.TemplateResponse(
        "500.html", {"request": request}, status_code=exc.status_code
    )


@app.get(path="/favicon.ico", response_class=FileResponse, include_in_schema=False)
async def icon():
    return FileResponse("static/favicon.ico")


if __name__ == "__main__":
    uvicorn.run("main:app", host="192.168.2.157", port=80, reload=True)
