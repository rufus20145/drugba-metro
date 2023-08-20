import os
from datetime import datetime, time, timedelta
from typing import Annotated, Any

import sqlalchemy as sa
import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext

from db import Alchemy
from models.camp import Squad
from models.metro import Line, Station
from models.money import (
    Deposit,
    PurchaseStationRequest,
    RequestStatus,
    RequestType,
    SquadRequest,
    Transaction,
    TransactionStatus,
    Wallet,
    Withdrawal,
)
from models.users import (
    Camper,
    Counselor,
    MetroCamper,
    RegisterCode,
    Roles,
    Token,
    User,
)

url = os.getenv("DATABASE_URL")
if not url:
    raise RuntimeError("DATABASE_URL is not set")
app = FastAPI()  # docs_url=None, redoc_url=None, openapi_url=None
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=8)
alchemy = Alchemy(url)

available_after = time(20, 30)
available_until = time(23, 30)

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
        squad_q = sa.select(Squad).filter_by(number=number)
        squad = session.scalars(squad_q).one_or_none()
        if not squad:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Состава с таким номером не найдено",
            )
        return templates.TemplateResponse(
            "squad.html",
            {"request": request, "squad": squad},
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
            with alchemy.session_scope() as session:
                query = sa.select(User).filter_by(username=token.username)
                user = session.scalars(query).one_or_none()
                if user:
                    return RedirectResponse(
                        "/profile", status_code=status.HTTP_302_FOUND
                    )
    response = templates.TemplateResponse("login.html", {"request": request})
    response.delete_cookie("token")
    return response


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
            with alchemy.session_scope() as session:
                query = sa.select(User).filter_by(username=token.username)
                user = session.scalars(query).one_or_none()
                if user:
                    return RedirectResponse(
                        "/profile", status_code=status.HTTP_302_FOUND
                    )
    with alchemy.session_scope() as session:
        roles = [Roles.COUNSELOR, Roles.CAMPER]
        squads_q = sa.select(Squad)
        squads = list(session.scalars(squads_q))
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
):
    token_str = request.cookies.get("token")
    if token_str:
        token = parse_token(token_str)
        if token and token.is_valid():
            return RedirectResponse("/profile", status_code=status.HTTP_302_FOUND)

    role = Roles[role_str]
    with alchemy.session_scope() as session:
        user_q = sa.select(User).filter_by(username=username)
        user = session.scalars(user_q).one_or_none()
        if user:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Пользователь с таким логином уже существует"},
            )

        squad_q = sa.select(Squad).filter_by(number=squad_number)
        squad = session.scalars(squad_q).one_or_none()
        if not squad:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Состава с таким номером не найдено"},
            )

        reg_code_q = sa.select(RegisterCode).filter_by(code=code)
        reg_code = session.scalars(reg_code_q).one_or_none()

        if not reg_code:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Код не найден"},
            )

        match role:
            case Roles.COUNSELOR:
                if reg_code.created_by.role != Roles.METHODIST:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "message": "Данный код не предназначен для регистрации с данной ролью"
                        },
                    )
                if reg_code.target_squad.number != squad.number:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "message": "Данный код предназначен для другого состава"
                        },
                    )
                new_user = Counselor(username, pwd_context.hash(password), squad)
            case Roles.CAMPER:
                if reg_code.created_by.role != Roles.COUNSELOR:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "message": "Данный код не предназначен для регистрации с данной ролью"
                        },
                    )
                if reg_code.target_squad.number != squad.number:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "message": "Данный код предназначен для другого состава"
                        },
                    )
                new_user = Camper(username, pwd_context.hash(password), squad)
            case _:
                return JSONResponse(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    content={"message": "Неизвестная роль."},
                )
        session.add(new_user)
        response = JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"message": "Регистрация прошла успешно"},
        )
        token = create_access_token(username)
        response.set_cookie(
            "token", token, expires=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )
        return response


@app.get(path="/profile", response_class=HTMLResponse)
def get_profile_page(request: Request):
    login_redirect = RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    token_str = request.cookies.get("token")
    if not token_str:
        return login_redirect
    token = parse_token(token_str)
    if not token:
        return login_redirect
    if not token.is_valid():
        return login_redirect

    with alchemy.session_scope() as session:
        user_query = sa.select(User).filter_by(username=token.username)
        user = session.scalars(user_query).one_or_none()
        if not user:
            return login_redirect

        access_level = user.get_access_level()

        stations_q = sa.select(Station)
        stations = list(session.scalars(stations_q))

        free_stations_q = sa.select(Station).filter_by(owner_id=None)
        free_stations = list(session.scalars(free_stations_q))

        purchase_requests = sa.select(PurchaseStationRequest)
        purchase_requests = list(session.scalars(purchase_requests))

        squads_q = sa.select(Squad)
        squads = list(session.scalars(squads_q))

        transactions: list[Transaction] = []

        if (
            user.role == Roles.CAMPER
            or user.role == Roles.METRO_CAMPER
            or user.role == Roles.COUNSELOR
        ):
            user_2: Camper | MetroCamper | Counselor = user  # type: ignore
            transactions_q = (
                sa.select(Transaction)
                .filter_by(wallet_id=user_2.squad.wallet.id)
                .filter_by(status=TransactionStatus.COMPLETED)
            )
            transactions = list(session.scalars(transactions_q))

        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "access_level": access_level,
                "user": user,
                "stations": stations,
                "free_stations": free_stations,
                "squads": squads,
                "purchase_requests": purchase_requests,
                "transactions": transactions,
            },
        )


@app.get(path="/logout", response_class=RedirectResponse)
def logout():
    response = RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("token")
    return response


@app.post(path="/create-purchase-request", response_class=JSONResponse)
def create_purchase_request(
    request: Request,
    station_id: Annotated[int, Form()],
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

    with alchemy.session_scope() as session:
        user_q = sa.select(User).filter_by(username=token.username)
        user = session.scalars(user_q).one_or_none()
        if not user:
            return no_permission

        if user.role != Roles.COUNSELOR and user.role != Roles.METRO_CAMPER:
            return no_permission
        user_2: Counselor | MetroCamper = user  # type: ignore
        current_time = datetime.now().time()
        if current_time < available_after or current_time > available_until:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message": f"Создать заявку можно только в промежутке {available_after.strftime('%H:%M')} - {available_until.strftime('%H:%M')}."
                },
            )
        station_q = sa.select(Station).filter_by(id=station_id)
        station = session.scalars(station_q).one_or_none()
        if not station:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Станция не найдена"},
            )
        purchase_requests_q = sa.select(PurchaseStationRequest)
        purchase_requests = list(session.scalars(purchase_requests_q))
        sum = 0
        for purchase_request in purchase_requests:
            if purchase_request.station_id == station.id:
                if purchase_request.squad_id == user_2.squad_id:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"message": "Вы уже отправили эту заявку."},
                    )
                else:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "message": "Заявку на эту станцию уже отправил другой отряд."
                        },
                    )
            if (
                purchase_request.status == RequestStatus.CREATED
                and purchase_request.squad_id == user_2.squad_id
            ):
                sum += purchase_request.station.initial_price
        if sum + station.initial_price > user_2.squad.wallet.current_balance:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message": f"Вам не хватает дружбанов на эту станцию. Нужно ещё {sum + station.initial_price - user_2.squad.wallet.current_balance}."
                },
            )
        purchase_request = PurchaseStationRequest(user_2.squad, station)
        session.add(purchase_request)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"message": f"Заявка на покупку станции {station.name} создана."},
        )


@app.post(path="/get-code", response_class=JSONResponse)
def get_code(
    request: Request,
    squad_id: Annotated[int, Form()],
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

    with alchemy.session_scope() as session:
        user_q = sa.select(User).filter_by(username=token.username)
        user = session.scalars(user_q).one_or_none()
        if not user:
            return no_permission

        target_squad_q = sa.select(Squad).filter_by(id=squad_id)
        target_squad = session.scalars(target_squad_q).one_or_none()
        if not target_squad:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Состава с таким номером не найдено"},
            )

        register_code = RegisterCode(user, target_squad)
        session.add(register_code)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": f"Код для регистрации в {target_squad.number} составе — {register_code.code}."
            },
        )


@app.post(path="/admin/change-station-owner", response_class=JSONResponse)
def change_station_owner(
    request: Request,
    station_id: Annotated[int, Form()],
    squad_id: Annotated[int, Form()],
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

    with alchemy.session_scope() as session:
        user_q = sa.select(User).filter_by(username=token.username)
        user = session.scalars(user_q).one_or_none()
        if not user:
            return no_permission
        if user.role != Roles.ADMIN and user.role != Roles.METHODIST:
            return no_permission

        if squad_id == -1:
            return JSONResponse(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                content={"message": "Возврат временно не поддерживается."},
            )

        wallet_q = sa.select(Wallet).filter_by(squad_id=squad_id)
        wallet = session.scalars(wallet_q).one_or_none()
        if not wallet:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Состав не найден"},
            )
        station_q = sa.select(Station).filter_by(id=station_id)
        station = session.scalars(station_q).one_or_none()
        if not station:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Станция не найдена"},
            )
        if station.owner_id:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
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
                status_code=status.HTTP_201_CREATED,
                content={
                    "message": f"Станция {station.name} куплена {squad_id} отрядом за {station.initial_price} дружбанов"
                },
            )
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST, content={"message": str(e)}
            )


@app.post(path="/admin/add-balance", response_class=JSONResponse)
def add_balance(
    request: Request,
    squad_id: Annotated[int, Form()],
    type: Annotated[str, Form()],
    amount: Annotated[int, Form()],
    reason: Annotated[str, Form()],
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

    with alchemy.session_scope() as session:
        user_q = sa.select(User).filter_by(username=token.username)
        user = session.scalars(user_q).one_or_none()
        if not user:
            return no_permission
        if user.role != Roles.ADMIN and user.role != Roles.METHODIST:
            return no_permission

        wallet_q = sa.select(Wallet).filter_by(squad_id=squad_id)
        wallet = session.scalars(wallet_q).one_or_none()
        if not wallet:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Состав не найден"},
            )
        old_balance = wallet.current_balance
        try:
            if type == "deposit":
                deposit = Deposit(
                    wallet=wallet, amount=amount, reason=reason, made_by=user
                )
                session.add(deposit)
                deposit.execute()
            elif type == "withdraw":
                withdrawal = Withdrawal(
                    wallet=wallet, amount=amount, reason=reason, made_by=user
                )
                session.add(withdrawal)
                withdrawal.execute()
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


@app.post(path="/process-request", response_class=JSONResponse)
def process_request(
    request: Request,
    request_id: Annotated[int, Form()],
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

    with alchemy.session_scope() as session:
        user_q = sa.select(User).filter_by(username=token.username)
        user = session.scalars(user_q).one_or_none()
        if not user:
            return no_permission
        if user.role != Roles.ADMIN and user.role != Roles.METHODIST:
            return no_permission

        squad_request_q = sa.select(SquadRequest).filter_by(id=request_id)
        squad_request = session.scalars(squad_request_q).one_or_none()

        if not squad_request:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Запрос не найден"},
            )

        if squad_request.status != RequestStatus.CREATED:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Запрос уже был обработан."},
            )

        match squad_request.type:
            case RequestType.STATION_PURCHASE:
                purchase_request: PurchaseStationRequest = squad_request  # type: ignore
                response = change_station_owner(
                    request, purchase_request.station_id, purchase_request.squad_id
                )
                if response.status_code == status.HTTP_201_CREATED:
                    purchase_request.status = RequestStatus.APPROVED
                    session.merge(purchase_request)
                return response
            case _:
                return JSONResponse(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    content={
                        "message": "Обработка других запросов будет реализована позже."
                    },
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
