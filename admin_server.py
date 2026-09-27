"""ASGI entry point for the extracted CareStance admin service."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routes.admin import router as admin_router


app = FastAPI(title="CareStance Admin", docs_url="/admin/docs", redoc_url="/admin/redoc")
app.include_router(admin_router)

BASE_DIR = Path(__file__).resolve().parent
ADMIN_LOGIN_URL = os.getenv("ADMIN_LOGIN_URL", "https://carestance.in/login")
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend" / "static"), name="static")


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/admin/", status_code=307)


@app.get("/login", include_in_schema=False)
async def login_redirect() -> RedirectResponse:
    return RedirectResponse(url=ADMIN_LOGIN_URL, status_code=307)