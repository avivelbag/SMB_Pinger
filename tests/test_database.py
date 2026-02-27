from pathlib import Path

import aiosqlite
import pytest

from smb_pinger.database import get_db, init_db


@pytest.mark.asyncio
async def test_init_db_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    await init_db(db_path)
    assert db_path.exists()

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]

    assert "businesses" in tables
    assert "ping_results" in tables
    assert "uptime_cache" in tables


@pytest.mark.asyncio
async def test_init_db_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    await init_db(db_path)
    await init_db(db_path)  # Should not raise


@pytest.mark.asyncio
async def test_get_db_context_manager(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    await init_db(db_path)
    async with get_db(db_path) as db:
        # Check WAL mode is set
        cursor = await db.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        assert row[0] == "wal"


@pytest.mark.asyncio
async def test_soft_delete_trigger(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    await init_db(db_path)
    async with get_db(db_path) as db:
        await db.execute(
            "INSERT INTO businesses (name, url, normalized_url) VALUES (?, ?, ?)",
            ("Test", "https://test.com", "https://test.com"),
        )
        await db.commit()
        with pytest.raises(aiosqlite.IntegrityError, match="Hard delete"):
            await db.execute("DELETE FROM businesses WHERE id = 1")
