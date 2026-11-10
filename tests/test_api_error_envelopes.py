from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


client = TestClient(app)


def test_validation_errors_use_standard_error_envelope():
    response = client.get("/api/v1/onchain/evm/wallets")
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"]
    assert response.headers["X-Request-ID"] == body["request_id"]
    assert len(body["request_id"]) == 32
    assert body["error"]["details"]
    assert "input" not in body["error"]["details"][0]


def test_not_found_uses_standard_error_envelope():
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "The requested resource was not found."


def test_http_exception_detail_is_preserved_as_structured_reason():
    contract = "0x" + "1" * 40
    response = client.get(
        f"/api/v1/onchain/evm/token/{contract}/history",
        params={"from_block": 10, "to_block": 1},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["reason"] == "to_block must be >= from_block"


def test_successful_response_also_includes_request_id_header():
    response = client.get("/api/v1/analysis/futures/liquidations/status")
    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 32



def test_private_api_rejects_missing_or_invalid_bearer_key(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", "test-owner-key-with-enough-entropy")
    missing = client.get("/api/v1/analysis/futures/liquidations/status")
    invalid = client.get(
        "/api/v1/analysis/futures/liquidations/status",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.json()["error"]["code"] == "UNAUTHORIZED"
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert missing.headers["X-Request-ID"] == missing.json()["request_id"]


def test_private_api_accepts_valid_bearer_key(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", "test-owner-key-with-enough-entropy")
    response = client.get(
        "/api/v1/analysis/futures/liquidations/status",
        headers={"Authorization": "Bearer test-owner-key-with-enough-entropy"},
    )
    assert response.status_code == 200


def test_production_api_fails_closed_without_strong_key(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "personal_api_key", "")
    response = client.get("/api/v1/analysis/futures/liquidations/status")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"



def test_each_private_ai_client_can_use_its_own_key(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", "")
    monkeypatch.setattr(
        settings,
        "ai_client_api_keys",
        '{"chatgpt":"chatgpt-test-key-12345678901234567890123456789012",'
        '"gemini":"gemini-test-key-12345678901234567890123456789012",'
        '"manus":"manus-test-key-12345678901234567890123456789012",'
        '"claude":"claude-test-key-12345678901234567890123456789012",'
        '"perplexity":"perplexity-test-key-12345678901234567890123456789012"}',
    )
    for client_name, key in (
        ("chatgpt", "chatgpt-test-key-12345678901234567890123456789012"),
        ("gemini", "gemini-test-key-12345678901234567890123456789012"),
        ("manus", "manus-test-key-12345678901234567890123456789012"),
        ("claude", "claude-test-key-12345678901234567890123456789012"),
        ("perplexity", "perplexity-test-key-12345678901234567890123456789012"),
    ):
        response = client.get(
            "/api/v1/analysis/futures/liquidations/status",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "DISABLED"


def test_unknown_ai_client_key_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", "")
    monkeypatch.setattr(
        settings,
        "ai_client_api_keys",
        '{"chatgpt":"chatgpt-test-key-12345678901234567890123456789012"}',
    )
    response = client.get(
        "/api/v1/analysis/futures/liquidations/status",
        headers={"Authorization": "Bearer unknown-client-key"},
    )
    assert response.status_code == 401
