from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
import app.main as main_module


client = TestClient(app)
TEST_API_KEY = "database-health-test-owner-key-with-sufficient-entropy"


def _authorize(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", TEST_API_KEY)
    monkeypatch.setattr(settings, "ai_client_api_keys", "{}")


def test_database_health_requires_private_bearer_key(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(settings, "database_url", "postgresql://user:password@db.example/neondb")

    response = client.get("/api/v1/system/database/health")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_database_health_returns_available_after_read_only_query(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(settings, "database_url", "postgresql://user:password@db.example/neondb")
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (1,)
    connect = MagicMock()
    connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(main_module.psycopg, "connect", connect)

    response = client.get(
        "/api/v1/system/database/health",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "available",
        "check": "SELECT 1",
    }
    connect.assert_called_once_with(
        settings.database_url,
        connect_timeout=5,
    )
    connection.execute.assert_called_once_with("SELECT 1")


def test_database_health_fails_closed_when_database_url_is_missing(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(settings, "database_url", "")

    response = client.get(
        "/api/v1/system/database/health",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "connection string" not in response.text.lower()


def test_database_health_does_not_expose_connection_error_or_credentials(monkeypatch):
    _authorize(monkeypatch)
    secret_url = "postgresql://private-user:private-password@db.example/neondb"
    monkeypatch.setattr(settings, "database_url", secret_url)

    def fail_connect(*args, **kwargs):
        raise RuntimeError(f"connection failed for {secret_url}")

    monkeypatch.setattr(main_module.psycopg, "connect", fail_connect)

    response = client.get(
        "/api/v1/system/database/health",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )

    assert response.status_code == 503
    assert secret_url not in response.text
    assert "private-password" not in response.text
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
