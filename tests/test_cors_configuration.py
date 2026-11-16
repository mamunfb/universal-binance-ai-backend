import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import configure_cors_middleware, parse_cors_allowed_origins
from app.main import request_tracking_middleware, settings


TEST_API_KEY = "qa-private-bearer-key-that-is-at-least-32-characters"


def _client(origins: str) -> TestClient:
    app = FastAPI()
    app.middleware("http")(request_tracking_middleware)
    # Added after request tracking so CORS middleware is the outer ASGI layer.
    configure_cors_middleware(app, origins)

    @app.get("/api/qa-probe")
    def protected_probe():
        return {"status": "ok"}

    return TestClient(app)


@pytest.fixture
def private_api_key(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", TEST_API_KEY)
    monkeypatch.setattr(settings, "ai_client_api_keys", "{}")


def test_parse_cors_allowed_origins_accepts_exact_https_and_localhost_origins():
    assert parse_cors_allowed_origins(
        " https://dashboard.example,https://research.example,http://localhost:3000,https://dashboard.example "
    ) == [
        "https://dashboard.example",
        "https://research.example",
        "http://localhost:3000",
    ]


def test_parse_cors_allowed_origins_normalizes_case_and_default_ports():
    assert parse_cors_allowed_origins(
        "HTTPS://Dashboard.Example:443,http://LOCALHOST:80,https://research.example:8443"
    ) == [
        "https://dashboard.example",
        "http://localhost",
        "https://research.example:8443",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "*",
        "https://*.pages.dev",
        "http://dashboard.example",
        "https://dashboard.example/",
        "https://dashboard.example/path",
        "https://user:password@dashboard.example",
        "https://dashboard.example?token=secret",
        "https://dashboard.example#fragment",
        "https://dashboard.example?",
        "https://dashboard.example#",
        "ftp://dashboard.example",
        "https://dashboard.example:invalid",
        "https://dashboard.example:65536",
        "https://dashboard.example:",
        "https://dashboard example",
    ],
)
def test_parse_cors_allowed_origins_rejects_unsafe_or_non_origin_values(value):
    with pytest.raises(ValueError):
        parse_cors_allowed_origins(value)


def test_allowed_dashboard_origin_passes_authorization_preflight_without_bearer_key(private_api_key):
    response = _client("https://dashboard.example").options(
        "/api/qa-probe",
        headers={
            "Origin": "https://dashboard.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://dashboard.example"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers


def test_unlisted_dashboard_origin_is_rejected_at_preflight(private_api_key):
    response = _client("https://dashboard.example").options(
        "/api/qa-probe",
        headers={
            "Origin": "https://unlisted.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_protected_api_rejects_missing_bearer_key_but_returns_cors_header(private_api_key):
    response = _client("https://dashboard.example").get(
        "/api/qa-probe",
        headers={"Origin": "https://dashboard.example"},
    )

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "https://dashboard.example"
    assert response.headers["www-authenticate"] == "Bearer"


def test_protected_api_rejects_invalid_bearer_key(private_api_key):
    response = _client("https://dashboard.example").get(
        "/api/qa-probe",
        headers={
            "Origin": "https://dashboard.example",
            "Authorization": "Bearer invalid-qa-key",
        },
    )

    assert response.status_code == 401


def test_protected_api_accepts_valid_bearer_key_for_allowed_origin(private_api_key):
    response = _client("https://dashboard.example").get(
        "/api/qa-probe",
        headers={
            "Origin": "https://dashboard.example",
            "Authorization": f"Bearer {TEST_API_KEY}",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["access-control-allow-origin"] == "https://dashboard.example"


def test_empty_cors_configuration_does_not_grant_cross_origin_access(private_api_key):
    response = _client("").get(
        "/api/qa-probe",
        headers={
            "Origin": "https://dashboard.example",
            "Authorization": f"Bearer {TEST_API_KEY}",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers

@pytest.mark.parametrize("requested_method", ["PUT", "PATCH", "DELETE"])
def test_preflight_rejects_methods_outside_the_cors_allowlist(private_api_key, requested_method):
    response = _client("https://dashboard.example").options(
        "/api/qa-probe",
        headers={
            "Origin": "https://dashboard.example",
            "Access-Control-Request-Method": requested_method,
        },
    )

    assert response.status_code == 400
    assert response.headers["access-control-allow-origin"] == "https://dashboard.example"
    allowed_methods = response.headers["access-control-allow-methods"].upper().split(",")
    assert requested_method not in [method.strip() for method in allowed_methods]


def test_preflight_rejects_unlisted_request_headers(private_api_key):
    response = _client("https://dashboard.example").options(
        "/api/qa-probe",
        headers={
            "Origin": "https://dashboard.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-admin-override",
        },
    )

    assert response.status_code == 400
    assert response.headers["access-control-allow-origin"] == "https://dashboard.example"
    allowed_headers = response.headers["access-control-allow-headers"].lower().split(",")
    assert "x-admin-override" not in [header.strip() for header in allowed_headers]
