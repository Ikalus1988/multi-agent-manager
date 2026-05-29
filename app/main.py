from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routes.api import router as api_router
from app.routes.web import router as web_router

app = FastAPI(title="Multi Agent Manager")
app.include_router(api_router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="/mnt/c/Users/hp/multi-agent-manager/app/templates"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
