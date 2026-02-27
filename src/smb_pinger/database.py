import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """\
CREATE TABLE IF NOT EXISTS businesses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    normalized_url TEXT NOT NULL UNIQUE,
    category TEXT,
    address TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ping_results (
    id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    checked_at TEXT NOT NULL DEFAULT (datetime('now')),
    cycle_id TEXT NOT NULL,
    status_code INTEGER CHECK (status_code BETWEEN 100 AND 599),
    response_time_ms REAL CHECK (response_time_ms >= 0),
    is_up INTEGER NOT NULL CHECK (is_up IN (0, 1)),
    result TEXT NOT NULL CHECK (result IN ('up', 'down', 'timeout', 'dns_error',
                                           'ssl_error', 'redirect_loop', 'challenge_page')),
    error TEXT
);

CREATE TABLE IF NOT EXISTS uptime_cache (
    business_id INTEGER PRIMARY KEY REFERENCES businesses(id),
    current_status TEXT NOT NULL,
    uptime_24h REAL,
    uptime_7d REAL,
    uptime_30d REAL,
    last_checked_at TEXT,
    last_response_time_ms REAL,
    computed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ping_business_covering ON ping_results(
    business_id, checked_at DESC, is_up, response_time_ms, status_code, result
);
CREATE INDEX IF NOT EXISTS idx_ping_time_business_up ON ping_results(
    checked_at, business_id, is_up
);
CREATE INDEX IF NOT EXISTS idx_business_active ON businesses(is_active);

CREATE TRIGGER IF NOT EXISTS prevent_business_delete
BEFORE DELETE ON businesses
BEGIN
    SELECT RAISE(ABORT, 'Hard delete not allowed. Set is_active = 0 instead.');
END;
"""


def _get_pragma_settings() -> tuple[int, int]:
    """Return (cache_size, mmap_size) based on available RAM."""
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        phys_pages = os.sysconf("SC_PHYS_PAGES")
        total_mem_mb = page_size * phys_pages // (1024 * 1024)
    except (ValueError, OSError):
        total_mem_mb = 1024  # default to 1GB

    if total_mem_mb <= 1024:
        return -8000, 67_108_864  # 8MB cache, 64MB mmap
    return -16000, 134_217_728  # 16MB cache, 128MB mmap


async def _apply_pragmas(db: aiosqlite.Connection) -> None:
    cache_size, mmap_size = _get_pragma_settings()
    await db.execute("PRAGMA journal_mode = WAL")
    await db.execute("PRAGMA synchronous = NORMAL")
    await db.execute("PRAGMA busy_timeout = 5000")
    await db.execute(f"PRAGMA cache_size = {cache_size}")
    await db.execute(f"PRAGMA mmap_size = {mmap_size}")
    await db.execute("PRAGMA foreign_keys = ON")
    await db.execute("PRAGMA temp_store = MEMORY")


async def init_db(db_path: Path) -> None:
    """Create database file, apply PRAGMAs, and initialize schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await _apply_pragmas(db)
        await db.executescript(SCHEMA)
        await db.commit()
    logger.info("Database initialized at %s", db_path)


@asynccontextmanager
async def get_db(db_path: Path) -> AsyncIterator[aiosqlite.Connection]:
    """Yield an aiosqlite connection with PRAGMAs applied."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await _apply_pragmas(db)
        yield db
