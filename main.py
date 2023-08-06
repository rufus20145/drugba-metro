import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from connect import Alchemy

url = "mysql+pymysql://root:123456789@localhost:3306/metro"
app = FastAPI(docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
alchemy = Alchemy(url)


@app.get(path="/", response_class=HTMLResponse)
def root(request: Request):
    with alchemy.get_session() as session:
        lines = alchemy.get_all_lines(session)
        return templates.TemplateResponse(
            "index.html", {"request": request, "lines": lines}
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


if __name__ == "__main__":
    uvicorn.run("main:app", host="192.168.2.157", port=80, reload=True)
