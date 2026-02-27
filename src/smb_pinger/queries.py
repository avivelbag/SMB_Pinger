from typing import Any

import aiosqlite


async def get_dashboard_summary(db: aiosqlite.Connection) -> dict[str, int]:
    """Get summary counts for dashboard cards."""
    cursor = await db.execute(
        "SELECT COUNT(*) as total FROM businesses WHERE is_active = 1"
    )
    row = await cursor.fetchone()
    total = row["total"] if row else 0

    cursor = await db.execute(
        "SELECT COUNT(*) as up FROM uptime_cache WHERE current_status = 'up'"
    )
    row = await cursor.fetchone()
    up = row["up"] if row else 0

    cursor = await db.execute(
        "SELECT COUNT(*) as down FROM uptime_cache WHERE current_status != 'up'"
    )
    row = await cursor.fetchone()
    down = row["down"] if row else 0

    return {"total": total, "up": up, "down": down}


async def get_businesses_with_status(
    db: aiosqlite.Connection,
    *,
    sort_by: str = "name",
    sort_order: str = "asc",
    search: str = "",
    status_filter: str = "",
) -> list[dict[str, Any]]:
    """Get all active businesses with their uptime cache data."""
    allowed_sort = {"name", "current_status", "uptime_24h", "uptime_7d", "last_checked_at"}
    if sort_by not in allowed_sort:
        sort_by = "name"
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"

    query = """
        SELECT b.id, b.name, b.url, b.category,
               COALESCE(c.current_status, 'unknown') as current_status,
               c.uptime_24h, c.uptime_7d, c.uptime_30d,
               c.last_checked_at, c.last_response_time_ms
        FROM businesses b
        LEFT JOIN uptime_cache c ON c.business_id = b.id
        WHERE b.is_active = 1
    """
    params: list[Any] = []

    if search:
        query += " AND (b.name LIKE ? OR b.url LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])

    if status_filter == "down":
        query += " AND c.current_status != 'up'"
    elif status_filter == "up":
        query += " AND c.current_status = 'up'"

    query += f" ORDER BY {sort_by} {sort_order}"

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_down_businesses(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    """Get businesses that are currently down."""
    cursor = await db.execute("""
        SELECT b.id, b.name, b.url, c.current_status, c.last_checked_at
        FROM businesses b
        JOIN uptime_cache c ON c.business_id = b.id
        WHERE b.is_active = 1 AND c.current_status != 'up'
        ORDER BY c.last_checked_at DESC
    """)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_business_detail(
    db: aiosqlite.Connection, business_id: int
) -> dict[str, Any] | None:
    """Get full business details with cache data."""
    cursor = await db.execute(
        """SELECT b.*, c.current_status, c.uptime_24h, c.uptime_7d, c.uptime_30d,
                  c.last_checked_at, c.last_response_time_ms
           FROM businesses b
           LEFT JOIN uptime_cache c ON c.business_id = b.id
           WHERE b.id = ?""",
        (business_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_recent_checks(
    db: aiosqlite.Connection, business_id: int, limit: int = 50
) -> list[dict[str, Any]]:
    """Get recent ping results for a business."""
    cursor = await db.execute(
        """SELECT checked_at, status_code, response_time_ms, is_up, result, error
           FROM ping_results
           WHERE business_id = ?
           ORDER BY checked_at DESC
           LIMIT ?""",
        (business_id, limit),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_uptime_bar_data(
    db: aiosqlite.Connection, business_id: int, hours: int = 24
) -> list[dict[str, Any]]:
    """Get hourly uptime data for the uptime bar visualization."""
    cursor = await db.execute(
        """SELECT
               strftime('%Y-%m-%d %H:00', checked_at) as hour,
               ROUND(100.0 * SUM(is_up) / COUNT(*), 1) as uptime_pct,
               COUNT(*) as checks
           FROM ping_results
           WHERE business_id = ?
             AND checked_at >= datetime('now', ? || ' hours')
           GROUP BY strftime('%Y-%m-%d %H:00', checked_at)
           ORDER BY hour""",
        (business_id, f"-{hours}"),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_response_time_data(
    db: aiosqlite.Connection, business_id: int, hours: int = 24
) -> list[dict[str, Any]]:
    """Get response time data for Chart.js line chart."""
    if hours <= 168:  # 7 days: raw data
        cursor = await db.execute(
            """SELECT checked_at as time, response_time_ms
               FROM ping_results
               WHERE business_id = ? AND response_time_ms IS NOT NULL
                 AND checked_at >= datetime('now', ? || ' hours')
               ORDER BY checked_at""",
            (business_id, f"-{hours}"),
        )
    else:  # 30+ days: hourly averages
        cursor = await db.execute(
            """SELECT strftime('%Y-%m-%d %H:00', checked_at) as time,
                      ROUND(AVG(response_time_ms), 1) as response_time_ms
               FROM ping_results
               WHERE business_id = ? AND response_time_ms IS NOT NULL
                 AND checked_at >= datetime('now', ? || ' hours')
               GROUP BY strftime('%Y-%m-%d %H:00', checked_at)
               ORDER BY time""",
            (business_id, f"-{hours}"),
        )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_all_businesses(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    """Get all businesses for admin page (including inactive)."""
    cursor = await db.execute(
        """SELECT b.*, c.current_status, c.last_checked_at
           FROM businesses b
           LEFT JOIN uptime_cache c ON c.business_id = b.id
           ORDER BY b.is_active DESC, b.name"""
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
