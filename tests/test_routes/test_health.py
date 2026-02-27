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


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
