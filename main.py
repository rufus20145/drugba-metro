import os
from datetime import datetime, timedelta
from typing import Annotated, Any

import sqlalchemy as sa
import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext

from db import Alchemy
from models import Admin, Line, Roles, Squad, Station, Token, User
from models.money import Deposit, Transaction, TransactionStatus, Wallet, Withdrawal

url = os.getenv("DATABASE_URL")
if not url:
    raise RuntimeError("DATABASE_URL is not set")
app = FastAPI()  # docs_url=None, redoc_url=None, openapi_url=None
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
alchemy = Alchemy(url)

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
        # parse token str and get username and exp
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        tkn = Token(**payload)
        return tkn
    except JWTError as e:
        print(e)
        return None


@app.get(path="/", response_class=HTMLResponse)
def get_root_page(request: Request):
    with alchemy.session_scope() as session:
        lines_query = sa.select(Line).order_by(Line.order_number)
        lines = list(session.scalars(lines_query))

        squads_query = sa.select(Squad)
        squads = list(session.scalars(squads_query))

        return templates.TemplateResponse(
            "index.html", {"request": request, "lines": lines, "squads": squads}
        )


@app.get("/bought-stations", response_class=HTMLResponse)
def get_bought_stations_page(request: Request):
    with alchemy.session_scope() as session:
        query = sa.select(Station).where(Station.owner_id != None)
        bought_stations = list(session.scalars(query))
        return templates.TemplateResponse(
            "bought-stations.html",
            {"request": request, "bought_stations": bought_stations},
        )


@app.get(path="/squad/{number}", response_class=HTMLResponse)
def get_squad_info(request: Request, number: int):
    with alchemy.session_scope() as session:
        squad_q = sa.select(Squad).filter_by(name=number)
        squad = session.scalars(squad_q).one_or_none()
        if not squad:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Состава с таким номером не найдено",
            )
        transactions_q = (
            sa.select(Transaction)
            .filter_by(wallet_id=squad.wallet.id)
            .filter_by(status=TransactionStatus.COMPLETED)
        )
        transactions = list(session.scalars(transactions_q))
        return templates.TemplateResponse(
            "squad.html",
            {"request": request, "squad": squad, "transactions": transactions},
        )


@app.get(path="/line/{number}", response_class=HTMLResponse)
def get_line_info(request: Request, number: str):
    with alchemy.session_scope() as session:
        query = sa.select(Line).filter_by(number=number)
        line = session.scalars(query).one_or_none()
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Линия с таким номером не найдена",
            )
        return templates.TemplateResponse(
            "line.html", {"request": request, "line": line}
        )


@app.get(path="/login", response_class=HTMLResponse)
def get_auth_page(request: Request):
    token_str = request.cookies.get("token")
    if token_str:
        token = parse_token(token_str)
        if token and token.is_valid():
            return RedirectResponse("/profile", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse("login.html", {"request": request})


@app.post(path="/login", response_class=JSONResponse)
def login(
    request: Request, username: Annotated[str, Form()], password: Annotated[str, Form()]
):
    token_str = request.cookies.get("token")
    if token_str:
        token = parse_token(token_str)
        if token and token.is_valid():
            return RedirectResponse("/profile", status_code=status.HTTP_302_FOUND)

    with alchemy.session_scope() as session:
        query = sa.select(User).filter_by(username=username)
        user = session.scalars(query).one_or_none()
        if not user:
            return JSONResponse(
                status_code=401, content={"message": "Неверный логин или пароль"}
            )
        if not pwd_context.verify(password, user.pwd_hash):
            return JSONResponse(
                status_code=401, content={"message": "Неверный логин или пароль"}
            )
        response = JSONResponse(
            status_code=200, content={"message": "Авторизация прошла успешно"}
        )
        token = create_access_token(user.username)
        response.set_cookie(
            "token", token, expires=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )
        return response


@app.get(path="/register", response_class=HTMLResponse)
def get_register_page(request: Request):
    token_str = request.cookies.get("token")
    if token_str:
        token = parse_token(token_str)
        if token and token.is_valid():
            return RedirectResponse("/profile", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse("register.html", {"request": request})


@app.post(path="/register", response_class=JSONResponse)
def register(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    role: Annotated[str, Form()],
):
    token_str = request.cookies.get("token")
    if token_str:
        token = parse_token(token_str)
        if token and token.is_valid():
            return RedirectResponse("/profile", status_code=status.HTTP_302_FOUND)

    with alchemy.session_scope() as session:
        query = sa.select(User).filter_by(username=username)
        user = session.scalars(query).one_or_none()
        if user:
            return JSONResponse(
                status_code=400,
                content={"message": "Пользователь с таким логином уже существует"},
            )

        match role:
            case Roles.ADMIN:
                new_user = Admin(username=username, pwd_hash=pwd_context.hash(password))
                session.add(
                    new_user
                )  # переместить после match, когда будет полноценная регистрация
            case Roles.METHODIST:
                pass

        response = JSONResponse(
            status_code=200, content={"message": "Регистрация прошла успешно"}
        )
        token = create_access_token(username)
        response.set_cookie(
            "token", token, expires=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )
        return response


@app.get(path="/profile", response_class=HTMLResponse)
def get_profile_page(request: Request):
    token_str = request.cookies.get("token")
    if not token_str:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    token = parse_token(token_str)
    if not token:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    if not token.is_valid():
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    with alchemy.session_scope() as session:
        user_query = sa.select(User).filter_by(username=token.username)
        user = session.scalars(user_query).one_or_none()

        if not user:
            return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

        if user.role == Roles.ADMIN or user.role == Roles.METHODIST:
            stations_q = sa.select(Station)
            stations = list(session.scalars(stations_q))

            squads_q = sa.select(Squad)
            squads = list(session.scalars(squads_q))
            return templates.TemplateResponse(
                "admin.html",
                {
                    "request": request,
                    "user": user,
                    "stations": stations,
                    "squads": squads,
                },
            )


@app.get(path="/logout", response_class=RedirectResponse)
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("token")
    return response


@app.post(path="/admin/change-station-owner", response_class=JSONResponse)
def change_station_owner(
    request: Request,
    station_id: Annotated[int, Form()],
    squad_id: Annotated[int, Form()],
):
    token_str = request.cookies.get("token")
    if not token_str:
        return JSONResponse(status_code=401, content={"message": "No permission"})

    token = parse_token(token_str)
    if not token:
        return JSONResponse(status_code=401, content={"message": "No permission"})

    if not token.is_valid():
        return JSONResponse(status_code=401, content={"message": "No permission"})

    with alchemy.session_scope() as session:
        user_q = sa.select(User).filter_by(username=token.username)
        user = session.scalars(user_q).one_or_none()
        if not user:
            return JSONResponse(status_code=401, content={"message": "No permission"})
        if user.role != Roles.ADMIN and user.role != Roles.METHODIST:
            return JSONResponse(status_code=401, content={"message": "No permission"})

        wallet_q = sa.select(Wallet).filter_by(squad_id=squad_id)
        wallet = session.scalars(wallet_q).one_or_none()
        if not wallet:
            return JSONResponse(
                status_code=401, content={"message": "Состав не найден"}
            )
        station_q = sa.select(Station).filter_by(id=station_id)
        station = session.scalars(station_q).one_or_none()
        if not station:
            return JSONResponse(
                status_code=401, content={"message": "Станция не найдена"}
            )
        if station.owner_id:
            return JSONResponse(
                status_code=401,
                content={
                    "message": "Станция уже куплена. Перепродажа будет реализована позже."
                },
            )
        try:
            withdrawal = Withdrawal(
                wallet=wallet,
                amount=station.initial_price,
                reason=f"Покупка станции {station.name}",
                made_by=user,
            )
            session.add(withdrawal)
            withdrawal.execute()
            station.owner_id = squad_id
            session.merge(station)
            return JSONResponse(
                status_code=201,
                content={
                    "message": f"Станция {station.name} куплена {squad_id} отрядом за {station.initial_price} дружбанов"
                },
            )
        except ValueError as e:
            return JSONResponse(status_code=400, content={"message": str(e)})


@app.post(path="/admin/add-balance", response_class=JSONResponse)
def add_balance(
    request: Request,
    squad_id: Annotated[int, Form()],
    type: Annotated[str, Form()],
    amount: Annotated[int, Form()],
    reason: Annotated[str, Form()],
):
    token_str = request.cookies.get("token")
    if not token_str:
        return JSONResponse(status_code=401, content={"message": "No permission"})

    token = parse_token(token_str)
    if not token:
        return JSONResponse(status_code=401, content={"message": "No permission"})

    if not token.is_valid():
        return JSONResponse(status_code=401, content={"message": "No permission"})

    with alchemy.session_scope() as session:
        user_q = sa.select(User).filter_by(username=token.username)
        user = session.scalars(user_q).one_or_none()
        if not user:
            return JSONResponse(status_code=401, content={"message": "No permission"})
        if user.role != Roles.ADMIN and user.role != Roles.METHODIST:
            return JSONResponse(status_code=401, content={"message": "No permission"})

        wallet_q = sa.select(Wallet).filter_by(squad_id=squad_id)
        wallet = session.scalars(wallet_q).one_or_none()
        if not wallet:
            return JSONResponse(
                status_code=401, content={"message": "Состав не найден"}
            )
        old_balance = wallet.current_balance
        try:
            if type == "deposit":
                deposit = Deposit(
                    wallet=wallet, amount=amount, reason=reason, made_by=user
                )
                session.add(deposit)
                deposit.execute()
            elif type == "withdrawal":
                withdrawal = Withdrawal(
                    wallet=wallet, amount=amount, reason=reason, made_by=user
                )
                session.add(withdrawal)
                withdrawal.execute()
            return JSONResponse(
                status_code=201,
                content={
                    "message": f"Баланс {squad_id} отряда успешно обновлен ({old_balance} -> {wallet.current_balance})"
                },
            )
        except ValueError as e:
            return JSONResponse(status_code=400, content={"message": str(e)})


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
