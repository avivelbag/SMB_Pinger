from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import pytest

from smb_pinger.config import Settings
from smb_pinger.database import SCHEMA, _apply_pragmas


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        db_path=tmp_path / "test.db",
        check_interval_minutes=1,
        concurrency_limit=5,
        timeout_seconds=5,
        admin_password_hash="$2b$12$test_hash_not_real",
    )


@pytest.fixture
async def db(settings: Settings) -> AsyncIterator[aiosqlite.Connection]:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await _apply_pragmas(conn)
        await conn.executescript(SCHEMA)
        await conn.commit()
        yield conn
