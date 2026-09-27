import asyncio
import importlib
import sys
from pathlib import Path

from sqlalchemy import inspect


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_init_db_creates_users_table_for_local_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "admin_local_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.delenv("VERCEL", raising=False)

    import app.database as database_module
    importlib.reload(database_module)

    import app.models  # noqa: F401

    asyncio.run(database_module.init_db())

    inspector = inspect(database_module.engine.sync_engine)
    assert "users" in inspector.get_table_names()
