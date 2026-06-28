from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routes.api import router as api_router
from app.routes.web import router as web_router

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"

app = FastAPI(title="Multi Agent Manager")
app.include_router(api_router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory=TEMPLATE_DIR), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
