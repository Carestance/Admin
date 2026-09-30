import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_init_db_creates_users_table_for_local_sqlite(tmp_path):
    db_path = tmp_path / "admin_local_test.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "sqlite+aiosqlite:///" + db_path.as_posix()
    environment.pop("VERCEL", None)
    script = """
import asyncio
from sqlalchemy import inspect
from app.database import engine, init_db

async def main():
    await init_db()
    async with engine.connect() as connection:
        tables = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )
    await engine.dispose()
    print('USERS_TABLE_EXISTS={}'.format('users' in tables))

asyncio.run(main())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT),
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "USERS_TABLE_EXISTS=True" in result.stdout
