import hashlib
from typing_extensions import Annotated
import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from db import Alchemy, Counselor, Pioneer, LogMessage

url = "mysql+pymysql://root:123456789@localhost:3306/metro"
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
alchemy = Alchemy(url)


@app.get(path="/", response_class=HTMLResponse)
def root(request: Request):
    with alchemy.get_session() as session:
        lines = alchemy.get_all_lines(session)
        squads = alchemy.get_all_squads(session)
        return templates.TemplateResponse(
            "index.html", {"request": request, "lines": lines, "squads": squads}
        )


@app.get(path="/line/{number}", response_class=HTMLResponse)
def line(request: Request, number: str):
    with alchemy.get_session() as session:
        line = alchemy.get_line_by_number(number, session)

        if line is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return templates.TemplateResponse(
            "line.html", {"request": request, "line": line}
        )


@app.get(path="/auth", response_class=HTMLResponse)
@app.get(path="/login", response_class=HTMLResponse)
def auth(request: Request):
    if request.cookies.get("token"):
        return RedirectResponse("/profile", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request})


@app.post(path="/auth", response_class=JSONResponse)
def auth(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    with alchemy.get_session() as session:
        user = alchemy.get_user_by_username(username, session)
        if user is None:
            return JSONResponse(
                status_code=401, content={"message": "Неверный логин или пароль"}
            )
        if user.pwd_hash != _hash(password):
            return JSONResponse(
                status_code=401, content={"message": "Неверный логин или пароль"}
            )
        response = JSONResponse(
            status_code=200, content={"message": "Авторизация прошла успешно"}
        )
        # тут добавить обновление токена
        token_str = alchemy.get_or_generate_token(user)
        response.set_cookie(
            key="token",
            value=token_str,
            expires=14 * 24 * 60 * 60,
        )
        return response


@app.get(path="/reg", response_class=HTMLResponse)
@app.get(path="/register", response_class=HTMLResponse)
def reg(request: Request):
    if request.cookies.get("token"):
        return RedirectResponse("/profile", status_code=302)

    return templates.TemplateResponse("register.html", {"request": request})


@app.post(path="/reg", response_class=JSONResponse)
def reg(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    role: Annotated[str, Form()],
    squadNumber: Annotated[int, Form()],
):
    if alchemy.get_user_by_username(username, alchemy.get_session()):
        return JSONResponse(
            status_code=401,
            content={"message": "Логин уже занят"},
        )

    if role == "pioneer":
        new_user = Pioneer(username, _hash(password), squadNumber)
    elif role == "counselor":
        new_user = Counselor(username, _hash(password), squadNumber)

    with alchemy.get_session() as session:
        session.add(new_user)
        session.commit()
        response = JSONResponse(
            status_code=201, content={"message": "Регистрация прошла успешно"}
        )
        token_str = alchemy.get_or_generate_token(new_user)
        response.set_cookie(
            key="token",
            value=token_str,
            expires=14 * 24 * 60 * 60,
        )
        return response


@app.get(path="/profile", response_class=HTMLResponse)
def profile(request: Request):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    user = alchemy.get_user_by_token(token)
    if user.role == "admin" or user.role == "methodist":
        with alchemy.get_session() as session:
            return templates.TemplateResponse(
                "admin.html",
                {
                    "request": request,
                    "user": user,
                    "stations": alchemy.get_all_stations(session=session),
                    "squads": alchemy.get_all_squads(session=session),
                },
            )
    if user.role == "admin" or user.role == "methodist":
        return templates.TemplateResponse(
            "methodist.html", {"request": request, "user": user}
        )
    return templates.TemplateResponse(
        "profile.html", {"request": request, "user": user}
    )


@app.get(path="/logout", response_class=RedirectResponse)
@app.get(path="/deauth", response_class=RedirectResponse)
def logout(request: Request):
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("token")
    return response


@app.post(path="/admin/change-station-owner", response_class=JSONResponse)
def change_station_owner(
    request: Request, station: Annotated[int, Form()], squad: Annotated[int, Form()]
):
    token = request.cookies.get("token")
    if not token:
        return JSONResponse(status_code=401, content={"message": "Нет доступа"})
    with alchemy.get_session() as session:
        old_owner = alchemy.change_station_owner(station, squad, session)
        log_message = LogMessage(
            username=alchemy.get_user_by_token(token).username,
            message=f"Changed owner of station {station} from {old_owner} to {squad}",
        )
        session.add(log_message)
        session.commit()
        return JSONResponse(status_code=201, content={"message": "Владелец изменен"})


@app.post(path="/admin/change-balance", response_class=JSONResponse)
def change_balance(
    request: Request, squad: Annotated[int, Form()], new_balance: Annotated[int, Form()]
):
    token = request.cookies.get("token")
    if not token:
        return JSONResponse(status_code=401, content={"message": "Нет доступа"})
    if squad > 18 or squad < 1 or new_balance < 0:
        return JSONResponse(
            status_code=400, content={"message": "Неверный номер отряда или баланс"}
        )
    with alchemy.get_session() as session:
        old_balance = alchemy.change_balance(squad, new_balance, session)
        log_message = LogMessage(
            username=alchemy.get_user_by_token(token).username,
            message=f"Changed balance of squad {squad} from {old_balance} to {new_balance}",
        )
        session.add(log_message)
        session.commit()
        return JSONResponse(status_code=201, content={"message": "Баланс изменен"})


@app.post(path="/admin/add-balance", response_class=JSONResponse)
def add_balance(
    request: Request, squad: Annotated[int, Form()], amount: Annotated[int, Form()]
):
    token = request.cookies.get("token")
    if not token:
        return JSONResponse(status_code=401, content={"message": "Нет доступа"})
    if squad > 18 or squad < 1 or amount < 0:
        return JSONResponse(
            status_code=400, content={"message": "Неверный номер отряда или баланс"}
        )
    with alchemy.get_session() as session:
        old_balance = alchemy.add_balance(squad, amount, session)
        log_message = LogMessage(
            username=alchemy.get_user_by_token(token).username,
            message=f"Added {amount} to balance of squad {squad}. Old balance: {old_balance}. New balance: {old_balance + amount}",
        )
        session.add(log_message)
        session.commit()
        return JSONResponse(status_code=201, content={"message": "Баланс изменен"})


# ======================================================================================
@app.exception_handler(HTTPException)
@app.exception_handler(404)
def page_not_found(request: Request, exc: HTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=exc.status_code
        )
    return templates.TemplateResponse(
        "500.html", {"request": request}, status_code=exc.status_code
    )


@app.get(path="/favicon.ico", response_class=FileResponse, include_in_schema=False)
async def icon():
    return FileResponse("static/favicon.ico")


def _hash(string: str) -> str:
    return hashlib.sha256(string.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    uvicorn.run("main:app", host="192.168.2.157", port=80, reload=True)
