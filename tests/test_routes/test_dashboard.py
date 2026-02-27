from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smb_pinger.config import Settings
from smb_pinger.main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        db_path=tmp_path / "test.db",
        check_interval_minutes=999,
        admin_password_hash="$2b$12$test",
    )


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    app = create_app(test_settings)
    with TestClient(app) as c:
        yield c


def test_dashboard_loads(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "SMB Pinger" in response.text
    assert "Total Sites" in response.text


def test_dashboard_partial_summary(client: TestClient) -> None:
    response = client.get("/?partial=summary")
    assert response.status_code == 200
    assert "summary-cards" in response.text


def test_dashboard_partial_table(client: TestClient) -> None:
    response = client.get("/?partial=table")
    assert response.status_code == 200
    assert "business-table-container" in response.text


def test_business_detail_not_found(client: TestClient) -> None:
    response = client.get("/business/999")
    assert response.status_code == 404
