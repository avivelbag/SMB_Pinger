import aiosqlite
import pytest

from smb_pinger.csv_importer import import_csv


@pytest.mark.asyncio
async def test_import_basic_csv(db: aiosqlite.Connection) -> None:
    csv_content = "name,url\nJoe's Coffee,https://joescoffee.com\nBob's Bikes,https://bobsbikes.com"
    result = await import_csv(csv_content, db, check_ssrf=False)
    assert result.imported == 2
    assert result.skipped == 0

    cursor = await db.execute("SELECT COUNT(*) FROM businesses")
    row = await cursor.fetchone()
    assert row[0] == 2


@pytest.mark.asyncio
async def test_import_with_optional_fields(db: aiosqlite.Connection) -> None:
    csv_content = "name,url,category,address\nJoe's,https://joes.com,Coffee,123 Main St"
    result = await import_csv(csv_content, db, check_ssrf=False)
    assert result.imported == 1

    cursor = await db.execute("SELECT category, address FROM businesses WHERE id = 1")
    row = await cursor.fetchone()
    assert row["category"] == "Coffee"
    assert row["address"] == "123 Main St"


@pytest.mark.asyncio
async def test_import_deduplicates_on_normalized_url(db: aiosqlite.Connection) -> None:
    csv_content = "name,url\nJoe's,https://joes.com\nJoe's Copy,http://www.joes.com/"
    result = await import_csv(csv_content, db, check_ssrf=False)
    assert result.imported == 1
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_import_missing_columns(db: aiosqlite.Connection) -> None:
    csv_content = "business_name,website\nJoe's,https://joes.com"
    result = await import_csv(csv_content, db, check_ssrf=False)
    assert result.errors
    assert "name" in result.errors[0].lower() or "url" in result.errors[0].lower()


@pytest.mark.asyncio
async def test_import_empty_name_skipped(db: aiosqlite.Connection) -> None:
    csv_content = "name,url\n,https://joes.com\nBob,https://bobs.com"
    result = await import_csv(csv_content, db, check_ssrf=False)
    assert result.imported == 1
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_import_strips_formula_chars(db: aiosqlite.Connection) -> None:
    csv_content = "name,url\n=EVIL(),https://evil.com\n+Bob,https://bobs.com"
    await import_csv(csv_content, db, check_ssrf=False)
    # "=EVIL()" becomes "EVIL()" after stripping, "+Bob" becomes "Bob"
    cursor = await db.execute("SELECT name FROM businesses ORDER BY id")
    rows = await cursor.fetchall()
    names = [row["name"] for row in rows]
    assert "EVIL()" in names
    assert "Bob" in names


@pytest.mark.asyncio
async def test_import_bytes_input(db: aiosqlite.Connection) -> None:
    csv_bytes = b"name,url\nTest,https://test.com"
    result = await import_csv(csv_bytes, db, check_ssrf=False)
    assert result.imported == 1


@pytest.mark.asyncio
async def test_import_file_too_large(db: aiosqlite.Connection) -> None:
    huge = b"name,url\n" + b"x,https://x.com\n" * 1_000_000
    result = await import_csv(huge, db, check_ssrf=False)
    assert result.errors
    assert "limit" in result.errors[0].lower()


@pytest.mark.asyncio
async def test_import_idempotent(db: aiosqlite.Connection) -> None:
    csv_content = "name,url\nTest,https://test.com"
    await import_csv(csv_content, db, check_ssrf=False)
    result = await import_csv(csv_content, db, check_ssrf=False)
    assert result.imported == 0
    assert result.skipped == 1

    cursor = await db.execute("SELECT COUNT(*) FROM businesses")
    row = await cursor.fetchone()
    assert row[0] == 1
