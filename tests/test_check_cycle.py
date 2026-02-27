import aiosqlite
import httpx
import pytest
import respx

from smb_pinger.check_cycle import check_all_sites, refresh_uptime_cache


@pytest.mark.asyncio
@respx.mock
async def test_check_all_sites_stores_results(db: aiosqlite.Connection) -> None:
    # Insert test businesses
    await db.execute(
        "INSERT INTO businesses (name, url, normalized_url) VALUES (?, ?, ?)",
        ("Test Biz", "https://test.com", "https://test.com"),
    )
    await db.commit()

    respx.get("https://test.com").mock(return_value=httpx.Response(200))

    async with httpx.AsyncClient() as client:
        await check_all_sites(db, client, concurrency=5, request_timeout=5)

    cursor = await db.execute("SELECT COUNT(*) FROM ping_results")
    row = await cursor.fetchone()
    assert row[0] == 1

    cursor = await db.execute("SELECT is_up, result FROM ping_results WHERE business_id = 1")
    row = await cursor.fetchone()
    assert row["is_up"] == 1
    assert row["result"] == "up"


@pytest.mark.asyncio
@respx.mock
async def test_check_all_sites_no_businesses(db: aiosqlite.Connection) -> None:
    async with httpx.AsyncClient() as client:
        await check_all_sites(db, client)
    # Should not raise, just log and return


@pytest.mark.asyncio
@respx.mock
async def test_check_all_sites_handles_failure(db: aiosqlite.Connection) -> None:
    await db.execute(
        "INSERT INTO businesses (name, url, normalized_url) VALUES (?, ?, ?)",
        ("Down Biz", "https://down.com", "https://down.com"),
    )
    await db.commit()

    respx.get("https://down.com").mock(return_value=httpx.Response(500))

    async with httpx.AsyncClient() as client:
        await check_all_sites(db, client, concurrency=5, request_timeout=5)

    cursor = await db.execute("SELECT is_up, result FROM ping_results WHERE business_id = 1")
    row = await cursor.fetchone()
    assert row["is_up"] == 0
    assert row["result"] == "down"


@pytest.mark.asyncio
@respx.mock
async def test_uptime_cache_refreshed(db: aiosqlite.Connection) -> None:
    await db.execute(
        "INSERT INTO businesses (name, url, normalized_url) VALUES (?, ?, ?)",
        ("Cached Biz", "https://cached.com", "https://cached.com"),
    )
    await db.commit()

    respx.get("https://cached.com").mock(return_value=httpx.Response(200))

    async with httpx.AsyncClient() as client:
        await check_all_sites(db, client, concurrency=5, request_timeout=5)

    cursor = await db.execute("SELECT * FROM uptime_cache WHERE business_id = 1")
    row = await cursor.fetchone()
    assert row is not None
    assert row["current_status"] == "up"
    assert row["uptime_24h"] == 100.0


@pytest.mark.asyncio
async def test_refresh_uptime_cache_no_results(db: aiosqlite.Connection) -> None:
    await db.execute(
        "INSERT INTO businesses (name, url, normalized_url) VALUES (?, ?, ?)",
        ("Empty Biz", "https://empty.com", "https://empty.com"),
    )
    await db.commit()

    await refresh_uptime_cache(db)

    cursor = await db.execute("SELECT * FROM uptime_cache WHERE business_id = 1")
    row = await cursor.fetchone()
    assert row is not None
    assert row["uptime_24h"] is None  # No checks yet
