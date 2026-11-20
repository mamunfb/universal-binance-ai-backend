from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


client = TestClient(app)


def test_dashboard_html_and_assets_are_public_but_api_stays_protected(monkeypatch):
    monkeypatch.setattr(settings, "personal_api_key", "x" * 40)
    monkeypatch.setattr(settings, "ai_client_api_keys", "{}")

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.headers["content-type"].startswith("text/html")
    assert 'href="/dashboard-assets/app.css"' in dashboard.text
    assert 'src="/dashboard-assets/chart.js"' in dashboard.text
    assert 'src="/dashboard-assets/app.js"' in dashboard.text

    css = client.get("/dashboard-assets/app.css")
    chart = client.get("/dashboard-assets/chart.js")
    script = client.get("/dashboard-assets/app.js")

    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert chart.status_code == 200
    assert "javascript" in chart.headers["content-type"]
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]

    protected_api = client.get("/api/v1/research/phase-readiness")
    assert protected_api.status_code == 401
