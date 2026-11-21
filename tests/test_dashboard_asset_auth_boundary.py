from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


client = TestClient(app)


def _configure_private_api(monkeypatch, *, environment: str = "development", key: str = "test-owner-key-with-enough-entropy") -> None:
    monkeypatch.setattr(settings, "app_env", environment)
    monkeypatch.setattr(settings, "personal_api_key", key)
    monkeypatch.setattr(settings, "ai_client_api_keys", "{}")


def test_dashboard_html_remains_public_when_api_authentication_is_configured(monkeypatch):
    _configure_private_api(monkeypatch)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "/dashboard-assets/app.css" in response.text
    assert "/dashboard-assets/chart.js" not in response.text
    assert "/dashboard-assets/app.js" in response.text
    app_script = client.get("/dashboard-assets/app.js")
    assert app_script.status_code == 200
    assert 'script.src="/dashboard-assets/chart.js"' in app_script.text


@pytest.mark.parametrize(
    ("asset_path", "expected_media_type"),
    [
        ("/dashboard-assets/app.css", "text/css"),
        ("/dashboard-assets/chart.js", "javascript"),
        ("/dashboard-assets/app.js", "javascript"),
    ],
)
def test_dashboard_assets_are_served_publicly_with_expected_content_type(
    monkeypatch, asset_path: str, expected_media_type: str
):
    _configure_private_api(monkeypatch)

    response = client.get(asset_path)

    assert response.status_code == 200
    assert expected_media_type in response.headers["content-type"].lower()
    assert response.content


def test_private_api_rejects_missing_bearer_key_while_dashboard_remains_public(monkeypatch):
    _configure_private_api(monkeypatch)

    dashboard = client.get("/dashboard")
    asset = client.get("/dashboard-assets/app.js")
    api = client.get("/api/v1/analysis/futures/liquidations/status")

    assert dashboard.status_code == 200
    assert asset.status_code == 200
    assert api.status_code == 401
    assert api.json()["error"]["code"] == "UNAUTHORIZED"
    assert api.headers["WWW-Authenticate"] == "Bearer"


def test_production_api_fails_closed_without_key_without_blocking_public_dashboard_assets(monkeypatch):
    _configure_private_api(monkeypatch, environment="production", key="")

    dashboard = client.get("/dashboard")
    asset = client.get("/dashboard-assets/app.css")
    api = client.get("/api/v1/analysis/futures/liquidations/status")

    assert dashboard.status_code == 200
    assert asset.status_code == 200
    assert api.status_code == 503
    assert api.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"


@pytest.mark.parametrize(
    "asset_path",
    [
        "/dashboard-assets/%2e%2e/backend/app/main.py",
        "/dashboard-assets/%2E%2E/backend/app/main.py",
        "/dashboard-assets/..%2f..%2fbackend/app/main.py",
        "/dashboard-assets/%252e%252e/backend/app/main.py",
    ],
)
def test_dashboard_static_mount_does_not_expose_files_outside_dashboard(
    monkeypatch, asset_path: str
):
    _configure_private_api(monkeypatch)

    response = client.get(asset_path)

    assert response.status_code == 404
    assert b"from fastapi import FastAPI" not in response.content


def test_dashboard_static_mount_does_not_enable_directory_listing(monkeypatch):
    _configure_private_api(monkeypatch)

    response = client.get("/dashboard-assets/")

    assert response.status_code == 404
