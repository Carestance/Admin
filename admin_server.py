"""ASGI entry point for the extracted CareStance admin service."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes.admin import router as admin_router


app = FastAPI(title="CareStance Admin", docs_url="/admin/docs", redoc_url="/admin/redoc")
app.include_router(admin_router)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    return {"status": "ok"}