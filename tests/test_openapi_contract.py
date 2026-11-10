from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_openapi_document_is_available_for_ai_clients():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert document["openapi"].startswith("3.")
    assert document["info"]["title"] == "Universal Binance AI Backend"
    assert "/api/v1/analysis/futures/liquidations/status" in document["paths"]


def test_openapi_documents_parameter_constraints():
    document = client.get("/openapi.json").json()
    operation = document["paths"]["/api/v1/markets/spot/klines/{symbol}"]["get"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 1000
    assert parameters["interval"]["schema"]["default"] == "1h"


def test_openapi_contains_research_only_api_description():
    document = client.get("/openapi.json").json()
    description = document["info"].get("description", "").lower()
    assert "research-only" in description
