from collections.abc import Iterator
from pathlib import Path

import bcrypt
import pytest
from fastapi.testclient import TestClient

from smb_pinger.config import Settings
from smb_pinger.main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    pw_hash = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode()
    return Settings(
        db_path=tmp_path / "test.db",
        check_interval_minutes=999,
        admin_password_hash=pw_hash,
    )


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    app = create_app(test_settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth() -> tuple[str, str]:
    return ("admin", "testpass")


def test_admin_requires_auth(client: TestClient) -> None:
    response = client.get("/admin")
    assert response.status_code == 401


def test_admin_loads_with_auth(
    client: TestClient, auth: tuple[str, str]
) -> None:
    response = client.get("/admin", auth=auth)
    assert response.status_code == 200
    assert "Admin" in response.text


def test_admin_wrong_password(client: TestClient) -> None:
    response = client.get("/admin", auth=("admin", "wrong"))
    assert response.status_code == 401


def test_add_business(
    client: TestClient, auth: tuple[str, str]
) -> None:
    response = client.post(
        "/admin/business",
        data={
            "name": "Test Biz",
            "url": "https://example.com",
            "category": "Test",
            "address": "123 Main St",
            "csrf_token": "test",
        },
        auth=auth,
        follow_redirects=False,
    )
    assert response.status_code == 303

    # Verify business was added
    response = client.get("/admin", auth=auth)
    assert "Test Biz" in response.text


def test_csv_import(
    client: TestClient, auth: tuple[str, str]
) -> None:
    csv_content = b"name,url\nCSV Biz,https://csvbiz.com"
    response = client.post(
        "/admin/import",
        files={"file": ("test.csv", csv_content, "text/csv")},
        data={"csrf_token": "test"},
        auth=auth,
        follow_redirects=False,
    )
    assert response.status_code == 303
