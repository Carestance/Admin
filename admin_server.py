"""ASGI entry point for the extracted CareStance admin service."""

import logging
import os
from pathlib import Path
from typing import Dict
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

load_dotenv()

from app.database import get_db
from app.models import User
from app.routes.admin import router as admin_router

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "frontend" / "templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key_for_sessions")

app = FastAPI(title="CareStance Admin", docs_url="/admin/docs", redoc_url="/admin/redoc")
app.add_middleware(
    SessionMiddleware,
    secret_key=JWT_SECRET_KEY,
    same_site="lax",
    https_only=os.getenv("SESSION_COOKIE_SECURE", "false").strip().lower() == "true",
)
app.include_router(admin_router)
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend" / "static"), name="static")

oauth = OAuth()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@app.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/admin/", status_code=307)


@app.get("/health", tags=["System"])
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={
            "error": request.query_params.get("error"),
            "google_login_enabled": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        },
    )


@app.get("/auth/google", include_in_schema=False)
async def google_login(request: Request):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return RedirectResponse(url="/login?error=Google+sign-in+is+not+configured", status_code=303)

    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip() or str(
        request.url_for("google_auth_callback")
    )
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback", name="google_auth_callback", include_in_schema=False)
async def google_auth_callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
        google_user = token.get("userinfo") or {}
    except Exception:
        logger.exception("Google admin sign-in failed during OAuth callback")
        return RedirectResponse(url="/login?error=Google+sign-in+failed", status_code=303)

    email = str(google_user.get("email") or "").strip().lower()
    if not email or google_user.get("email_verified") is not True:
        return RedirectResponse(url="/login?error=Verified+Google+email+required", status_code=303)

    try:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
    except SQLAlchemyError:
        logger.exception("Google admin sign-in database query failed")
        return RedirectResponse(url="/login?error=Admin+database+is+not+configured", status_code=303)

    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    is_admin = user and (
        (user.role or "").strip().lower() == "admin"
        or (admin_email and user.email.strip().lower() == admin_email)
    )
    if not is_admin or getattr(user, "is_suspended", False):
        logger.warning("Google sign-in denied for non-admin or suspended account: email=%s", email)
        return RedirectResponse(url="/login?error=This+Google+account+is+not+authorized+for+admin+access", status_code=303)

    token = jwt.encode({"sub": str(user.id)}, JWT_SECRET_KEY, algorithm="HS256")
    response = RedirectResponse(url="/admin/", status_code=303)
    response.set_cookie(
        "user_id",
        token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=60 * 60 * 8,
        path="/",
    )
    return response


@app.post("/login", include_in_schema=False)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    normalized_email = email.strip().lower()
    try:
        result = await db.execute(select(User).where(User.email == normalized_email))
    except SQLAlchemyError:
        logger.exception("Admin login database query failed")
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={"error": "Admin database is not configured. Set DATABASE_URL to the CareStance database and restart."},
            status_code=503,
        )

    user = result.scalar_one_or_none()
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    is_admin = user and (
        user.role == "admin"
        or (admin_email and user.email.strip().lower() == admin_email)
    )

    password_valid = False
    if user and user.hashed_password:
        try:
            password_valid = pwd_context.verify(password, user.hashed_password)
        except (ValueError, TypeError):
            password_valid = False

    if not is_admin or getattr(user, "is_suspended", False) or not password_valid:
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={"error": "Invalid administrator email or password."},
            status_code=401,
        )

    token = jwt.encode({"sub": str(user.id)}, JWT_SECRET_KEY, algorithm="HS256")
    response = RedirectResponse(url="/admin/", status_code=303)
    response.set_cookie(
        "user_id",
        token,
        httponly=True,
        secure=request.url.scheme == "https",
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