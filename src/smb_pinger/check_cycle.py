import asyncio
import logging
import uuid

import aiosqlite
import httpx

from smb_pinger.checker import check_site
from smb_pinger.models import CheckOutcome

logger = logging.getLogger(__name__)


async def _check_with_semaphore(
    sem: asyncio.Semaphore,
    business_id: int,
    url: str,
    client: httpx.AsyncClient,
    request_timeout: float,
    max_redirects: int,
) -> tuple[int, CheckOutcome]:
    """Check a single site with concurrency limiting."""
    async with sem:
        outcome = await check_site(
            url, client, request_timeout=request_timeout, max_redirects=max_redirects
        )
        return business_id, outcome


async def check_all_sites(
    db: aiosqlite.Connection,
    client: httpx.AsyncClient,
    *,
    concurrency: int = 30,
    request_timeout: float = 15.0,
    max_redirects: int = 5,
) -> None:
    """Run a full check cycle: fetch active businesses, check, store, refresh cache."""
    cycle_id = str(uuid.uuid4())
    logger.info("Starting check cycle %s", cycle_id)

    # Fetch active businesses
    cursor = await db.execute(
        "SELECT id, url FROM businesses WHERE is_active = 1"
    )
    businesses = await cursor.fetchall()

    if not businesses:
        logger.info("No active businesses to check")
        return

    logger.info("Checking %d businesses", len(businesses))

    # Run checks concurrently
    sem = asyncio.Semaphore(concurrency)
    tasks = [
        _check_with_semaphore(sem, row["id"], row["url"], client, request_timeout, max_redirects)
        for row in businesses
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Prepare batch insert
    rows: list[tuple[int, str, int | None, float | None, int, str, str | None]] = []
    for item in results:
        if isinstance(item, BaseException):
            logger.error("Unexpected error in check task: %s", item)
            continue
        business_id, outcome = item
        rows.append((
            business_id,
            cycle_id,
            outcome.status_code,
            outcome.response_time_ms,
            1 if outcome.result.is_up else 0,
            outcome.result.value,
            outcome.error,
        ))

    if rows:
        await db.executemany(
            """INSERT INTO ping_results
               (business_id, cycle_id, status_code, response_time_ms, is_up, result, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        await db.commit()

    logger.info("Cycle %s: checked %d, stored %d results", cycle_id, len(businesses), len(rows))

    # Refresh uptime cache
    await refresh_uptime_cache(db)


async def refresh_uptime_cache(db: aiosqlite.Connection) -> None:
    """Recompute uptime_cache for all active businesses."""
    await db.execute("DELETE FROM uptime_cache")
    await db.execute("""
        INSERT INTO uptime_cache (
            business_id, current_status, uptime_24h, uptime_7d, uptime_30d,
            last_checked_at, last_response_time_ms, computed_at
        )
        SELECT
            b.id,
            COALESCE(latest.result, 'down'),
            (SELECT ROUND(100.0 * SUM(is_up) / COUNT(*), 2)
             FROM ping_results
             WHERE business_id = b.id
               AND checked_at >= datetime('now', '-1 day')),
            (SELECT ROUND(100.0 * SUM(is_up) / COUNT(*), 2)
             FROM ping_results
             WHERE business_id = b.id
               AND checked_at >= datetime('now', '-7 days')),
            (SELECT ROUND(100.0 * SUM(is_up) / COUNT(*), 2)
             FROM ping_results
             WHERE business_id = b.id
               AND checked_at >= datetime('now', '-30 days')),
            latest.checked_at,
            latest.response_time_ms,
            datetime('now')
        FROM businesses b
        LEFT JOIN (
            SELECT business_id, result, checked_at, response_time_ms,
                   ROW_NUMBER() OVER (PARTITION BY business_id ORDER BY checked_at DESC) AS rn
            FROM ping_results
        ) latest ON latest.business_id = b.id AND latest.rn = 1
        WHERE b.is_active = 1
    """)
    await db.commit()
    logger.info("Uptime cache refreshed")
