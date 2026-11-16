import pytest

from app.config import configure_cors_middleware, parse_cors_allowed_origins
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(origins: str) -> TestClient:
    app = FastAPI()
    configure_cors_middleware(app, origins)

    @app.get("/resource")
    def resource():
        return {"status": "ok"}

    @app.post("/resource")
    def create_resource():
        return {"status": "created"}

    return TestClient(app)


def test_parse_cors_allowed_origins_accepts_exact_https_and_localhost_origins():
    assert parse_cors_allowed_origins(
        " https://dashboard.example,https://research.example,"
        "http://localhost:3000,https://dashboard.example "
    ) == [
        "https://dashboard.example",
        "https://research.example",
        "http://localhost:3000",
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
        "ftp://dashboard.example",
        "https://dashboard.example:invalid",
        "https://dashboard.example:65536",
    ],
)
def test_parse_cors_allowed_origins_rejects_unsafe_or_non_origin_values(value):
    with pytest.raises(ValueError):
        parse_cors_allowed_origins(value)


def test_allowed_dashboard_origin_passes_authorization_preflight():
    response = _client("https://dashboard.example").options(
        "/resource",
        headers={
            "Origin": "https://dashboard.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://dashboard.example"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers


def test_unlisted_dashboard_origin_is_rejected_at_preflight():
    response = _client("https://dashboard.example").options(
        "/resource",
        headers={
            "Origin": "https://unlisted.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_empty_cors_configuration_does_not_grant_cross_origin_access():
    response = _client("").get(
        "/resource",
        headers={"Origin": "https://dashboard.example"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
