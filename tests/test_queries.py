import aiosqlite
import pytest

from smb_pinger.queries import (
    get_all_businesses,
    get_business_detail,
    get_businesses_with_status,
    get_dashboard_summary,
    get_down_businesses,
    get_recent_checks,
    get_response_time_data,
    get_uptime_bar_data,
)


async def _seed_business(
    db: aiosqlite.Connection, name: str = "Test", url: str = "https://test.com"
) -> int:
    cursor = await db.execute(
        "INSERT INTO businesses (name, url, normalized_url) VALUES (?, ?, ?)",
        (name, url, url),
    )
    await db.commit()
    return cursor.lastrowid or 1


async def _seed_ping(db: aiosqlite.Connection, business_id: int, is_up: int = 1) -> None:
    await db.execute(
        """INSERT INTO ping_results
           (business_id, cycle_id, status_code, response_time_ms, is_up, result)
           VALUES (?, 'test', ?, ?, ?, ?)""",
        (business_id, 200 if is_up else 500, 100.0, is_up, "up" if is_up else "down"),
    )
    await db.commit()


async def _seed_cache(db: aiosqlite.Connection, business_id: int, status: str = "up") -> None:
    await db.execute(
        """INSERT OR REPLACE INTO uptime_cache
           (business_id, current_status, uptime_24h, uptime_7d, uptime_30d,
            last_checked_at, last_response_time_ms, computed_at)
           VALUES (?, ?, 100.0, 99.5, 99.0, datetime('now'), 100.0, datetime('now'))""",
        (business_id, status),
    )
    await db.commit()


@pytest.mark.asyncio
async def test_dashboard_summary(db: aiosqlite.Connection) -> None:
    biz_id = await _seed_business(db)
    await _seed_cache(db, biz_id, "up")

    summary = await get_dashboard_summary(db)
    assert summary["total"] == 1
    assert summary["up"] == 1
    assert summary["down"] == 0


@pytest.mark.asyncio
async def test_businesses_with_status(db: aiosqlite.Connection) -> None:
    biz_id = await _seed_business(db)
    await _seed_cache(db, biz_id, "up")

    businesses = await get_businesses_with_status(db)
    assert len(businesses) == 1
    assert businesses[0]["name"] == "Test"
    assert businesses[0]["current_status"] == "up"


@pytest.mark.asyncio
async def test_businesses_search(db: aiosqlite.Connection) -> None:
    await _seed_business(db, "Joe's Coffee", "https://joes.com")
    await _seed_business(db, "Bob's Bikes", "https://bobs.com")

    results = await get_businesses_with_status(db, search="joe")
    assert len(results) == 1
    assert results[0]["name"] == "Joe's Coffee"


@pytest.mark.asyncio
async def test_down_businesses(db: aiosqlite.Connection) -> None:
    biz_id = await _seed_business(db)
    await _seed_cache(db, biz_id, "down")

    down = await get_down_businesses(db)
    assert len(down) == 1


@pytest.mark.asyncio
async def test_business_detail(db: aiosqlite.Connection) -> None:
    biz_id = await _seed_business(db)
    detail = await get_business_detail(db, biz_id)
    assert detail is not None
    assert detail["name"] == "Test"


@pytest.mark.asyncio
async def test_business_detail_not_found(db: aiosqlite.Connection) -> None:
    detail = await get_business_detail(db, 999)
    assert detail is None


@pytest.mark.asyncio
async def test_recent_checks(db: aiosqlite.Connection) -> None:
    biz_id = await _seed_business(db)
    await _seed_ping(db, biz_id, is_up=1)
    await _seed_ping(db, biz_id, is_up=0)

    checks = await get_recent_checks(db, biz_id)
    assert len(checks) == 2


@pytest.mark.asyncio
async def test_uptime_bar_data(db: aiosqlite.Connection) -> None:
    biz_id = await _seed_business(db)
    await _seed_ping(db, biz_id)

    data = await get_uptime_bar_data(db, biz_id)
    assert len(data) >= 1
    assert data[0]["uptime_pct"] is not None


@pytest.mark.asyncio
async def test_response_time_data(db: aiosqlite.Connection) -> None:
    biz_id = await _seed_business(db)
    await _seed_ping(db, biz_id)

    data = await get_response_time_data(db, biz_id)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_all_businesses(db: aiosqlite.Connection) -> None:
    await _seed_business(db, "Active", "https://active.com")
    await _seed_business(db, "Inactive", "https://inactive.com")
    await db.execute("UPDATE businesses SET is_active = 0 WHERE name = 'Inactive'")
    await db.commit()

    all_biz = await get_all_businesses(db)
    assert len(all_biz) == 2
