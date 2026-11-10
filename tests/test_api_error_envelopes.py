from fastapi.testclient import TestClient

from app.main import app


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
