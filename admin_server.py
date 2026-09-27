"""ASGI entry point for the extracted CareStance admin service."""

import os
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.routes.admin import router as admin_router


app = FastAPI(title="CareStance Admin", docs_url="/admin/docs", redoc_url="/admin/redoc")
app.include_router(admin_router)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "frontend" / "templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key_for_sessions")
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend" / "static"), name="static")


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/admin/", status_code=307)


@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {"error": None})


@app.post("/login", include_in_schema=False)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    normalized_email = email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    is_admin = user and (user.role == "admin" or (admin_email and user.email.lower() == admin_email))

    password_valid = False
    if user and user.hashed_password:
        try:
            password_valid = pwd_context.verify(password, user.hashed_password)
        except (ValueError, TypeError):
            password_valid = False

    if not is_admin or getattr(user, "is_suspended", False) or not password_valid:
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"error": "Invalid administrator email or password."},
            status_code=401,
        )

    token = jwt.encode({"sub": str(user.id)}, JWT_SECRET_KEY, algorithm="HS256")
    response = RedirectResponse(url="/admin/", status_code=303)
    response.set_cookie(
        "user_id",
        token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 8,
        path="/",
    )
    return response


@app.post("/logout", include_in_schema=False)
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("user_id", path="/")
    return response