import csv
import io
import logging
from dataclasses import dataclass

import aiosqlite

from smb_pinger.schemas import BusinessCreate
from smb_pinger.url_utils import validate_url_safe

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_ROWS = 10_000
FORMULA_CHARS = {"=", "+", "-", "@"}


def _sanitize(value: str) -> str:
    """Strip leading formula-injection characters."""
    value = value.strip()
    while value and value[0] in FORMULA_CHARS:
        value = value[1:]
    return value.strip()


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


async def import_csv(
    content: str | bytes,
    db: aiosqlite.Connection,
    *,
    check_ssrf: bool = True,
) -> ImportResult:
    """Parse CSV content and insert businesses into the database.

    CSV format: name,url (required), category,address (optional).
    Returns an ImportResult with counts and per-row errors.
    """
    if isinstance(content, bytes):
        if len(content) > MAX_FILE_SIZE:
            return ImportResult(errors=[f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit"])
        content = content.decode("utf-8", errors="replace")
    elif len(content.encode("utf-8")) > MAX_FILE_SIZE:
        return ImportResult(errors=[f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit"])

    result = ImportResult()
    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames or "name" not in reader.fieldnames or "url" not in reader.fieldnames:
        return ImportResult(errors=["CSV must have 'name' and 'url' columns"])

    rows_to_insert: list[tuple[str, str, str, str | None, str | None]] = []

    for i, row in enumerate(reader, start=2):  # row 1 is header
        if i - 1 > MAX_ROWS:
            result.errors = result.errors or []
            result.errors.append(f"Stopped at row {MAX_ROWS}: max row limit reached")
            break

        name = _sanitize(row.get("name", ""))
        url = _sanitize(row.get("url", ""))
        category = _sanitize(row.get("category", "")) or None
        address = _sanitize(row.get("address", "")) or None

        try:
            biz = BusinessCreate(name=name, url=url, category=category, address=address)
        except Exception as exc:
            result.errors = result.errors or []
            result.errors.append(f"Row {i}: {exc}")
            result.skipped += 1
            continue

        if check_ssrf and not validate_url_safe(biz.url):
            result.errors = result.errors or []
            result.errors.append(f"Row {i}: URL failed safety check: {url}")
            result.skipped += 1
            continue

        rows_to_insert.append((
            biz.name,
            biz.url,
            biz.normalized_url,
            biz.category,
            biz.address,
        ))

    if not rows_to_insert:
        return result

    # Batch insert with INSERT OR IGNORE for idempotent imports
    cursor = await db.executemany(
        """INSERT OR IGNORE INTO businesses (name, url, normalized_url, category, address)
           VALUES (?, ?, ?, ?, ?)""",
        rows_to_insert,
    )
    await db.commit()

    result.imported = cursor.rowcount if cursor.rowcount >= 0 else 0
    result.skipped += len(rows_to_insert) - result.imported

    logger.info(
        "CSV import: %d imported, %d skipped, %d errors",
        result.imported,
        result.skipped,
        len(result.errors) if result.errors else 0,
    )
    return result
