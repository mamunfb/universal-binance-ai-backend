import json
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


def test_successful_response_also_includes_request_id_and_security_headers():
    response = client.get("/api/v1/analysis/futures/liquidations/status")
    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 32
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


def test_dashboard_response_disables_caching_and_prevents_framing():
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_unauthorized_early_response_includes_security_headers(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", "test-owner-key-with-enough-entropy")
    response = client.get("/api/v1/analysis/futures/liquidations/status")
    assert response.status_code == 401
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"



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



def test_production_accepts_strong_owner_key_when_client_key_json_is_invalid(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "personal_api_key", "test-owner-key-with-enough-entropy")
    monkeypatch.setattr(settings, "ai_client_api_keys", "{invalid-json")
    response = client.get(
        "/api/v1/analysis/futures/liquidations/status",
        headers={"Authorization": "Bearer test-owner-key-with-enough-entropy"},
    )
    assert response.status_code == 200


def test_production_rejects_partial_client_keys_without_strong_owner_key(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "personal_api_key", "")
    monkeypatch.setattr(
        settings,
        "ai_client_api_keys",
        '{"chatgpt":"chatgpt-test-key-12345678901234567890123456789012"}',
    )
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


def test_unknown_configured_client_name_cannot_authenticate(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", "")
    monkeypatch.setattr(
        settings,
        "ai_client_api_keys",
        '{"unknown":"unknown-client-key-12345678901234567890123456789012"}',
    )
    response = client.get(
        "/api/v1/analysis/futures/liquidations/status",
        headers={"Authorization": "Bearer unknown-client-key-12345678901234567890123456789012"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_duplicate_client_api_keys_are_rejected_as_ambiguous(monkeypatch):
    shared_key = "shared-client-key-12345678901234567890123456789012"
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", "")
    monkeypatch.setattr(
        settings,
        "ai_client_api_keys",
        json.dumps({"chatgpt": shared_key, "gemini": shared_key}),
    )
    response = client.get(
        "/api/v1/analysis/futures/liquidations/status",
        headers={"Authorization": f"Bearer {shared_key}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_evm_wallet_route_sanitizes_provider_exception(monkeypatch):
    import asyncio
    from app import main

    class FakeProvider:
        async def chain_id(self):
            raise RuntimeError("https://rpc.example/key=secret-token")

    monkeypatch.setattr(main, "get_evm_provider", lambda: FakeProvider())
    try:
        asyncio.run(main.evm_wallet_snapshots("0x" + "1" * 40))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 502
        detail = str(getattr(exc, "detail", ""))
        assert "ONCHAIN_PROVIDER_UNAVAILABLE" in detail
        assert "secret-token" not in detail
    else:
        raise AssertionError("Expected sanitized HTTP 502")


def test_derivatives_route_sanitizes_unexpected_provider_exception(monkeypatch):
    import asyncio
    from app import main

    class FakeProvider:
        market = "USD_M"

    async def fail_analysis(*args, **kwargs):
        raise RuntimeError("https://futures.example/key=private-secret")

    monkeypatch.setattr(main, "get_futures_provider", lambda market: FakeProvider())
    monkeypatch.setattr(main, "get_derivatives_intelligence", fail_analysis)
    try:
        asyncio.run(main.usdm_derivatives_intelligence("BTCUSDT"))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 502
        detail = str(getattr(exc, "detail", ""))
        assert "DERIVATIVES_ANALYSIS_UNAVAILABLE" in detail
        assert "private-secret" not in detail
    else:
        raise AssertionError("Expected sanitized HTTP 502")


def test_spot_futures_basis_route_returns_analysis(monkeypatch):
    from app import main

    async def fake_analysis(spot, futures, symbol):
        return {"status": "COMPLETED", "symbol": symbol.upper(),
                "price_comparison": {"basis_percent": 0.5}}

    monkeypatch.setattr(main, "analyze_spot_futures_basis", fake_analysis)
    response = client.get("/api/v1/analysis/spot-futures/basis/btcusdt")
    assert response.status_code == 200
    assert response.json()["symbol"] == "BTCUSDT"
    assert response.json()["price_comparison"]["basis_percent"] == 0.5


def test_spot_futures_basis_route_rejects_empty_symbol():
    response = client.get("/api/v1/analysis/spot-futures/basis/%20")
    assert response.status_code == 422


def test_market_evidence_route_aggregates_read_only_sections(monkeypatch):
    import asyncio
    from app import main

    class FakeSpot:
        async def klines(self, symbol, interval, limit):
            return [[i, "100", "102", "99", "101", "10", i + 1] for i in range(limit)]

    class FakeFutures:
        market = "USD_M"

    async def multi(*args, **kwargs):
        return {"status": "COMPLETED", "timeframes": {
            "1d": {"trend_structure": "BULLISH_STRUCTURE"},
            "4h": {"trend_structure": "BULLISH_STRUCTURE"},
        }}

    async def basis(*args, **kwargs):
        return {"status": "COMPLETED", "source": "test",
                "price_comparison": {"status": "COMPLETED", "basis": 1,
                                     "basis_percent": 0.5, "relationship": "FUTURES_PREMIUM"},
                "funding": {"status": "COMPLETED", "funding_rate": 0.0001,
                            "funding_time_ms": 123, "source": "test"}}

    async def derivatives(*args, **kwargs):
        return {"status": "COMPLETED", "sections": {}}

    async def catalysts(*args, **kwargs):
        return {"status": "COMPLETED", "items": []}

    monkeypatch.setattr(main, "get_spot_provider", lambda: FakeSpot())
    monkeypatch.setattr(main, "get_futures_provider", lambda market: FakeFutures())
    monkeypatch.setattr(main, "analyze_multiple_timeframes", multi)
    monkeypatch.setattr(main, "analyze_spot_futures_basis", basis)
    monkeypatch.setattr(main, "get_derivatives_intelligence", derivatives)
    monkeypatch.setattr(main, "news_catalysts", catalysts)
    monkeypatch.setattr(main, "calculate_vwap", lambda rows: {
        "status": "COMPLETED", "latest_vwap": 100, "latest_close": 101})
    monkeypatch.setattr(main, "calculate_volume_profile", lambda rows: {
        "status": "COMPLETED", "poc": {"price_mid": 100}, "vah": 102, "val": 99})
    monkeypatch.setattr(main, "analyze_market_structure", lambda rows: {
        "status": "COMPLETED", "trend_state": "BULLISH"})

    result = asyncio.run(main.market_evidence_snapshot("btcusdt"))
    assert result["status"] == "INCOMPLETE"
    assert result["symbol"] == "BTCUSDT"
    assert result["decision"]["status"] == "NO_TRADE_DECISION"
    assert result["decision"]["buy_sell_signal"] is None
    assert result["section_status"]["multi_timeframe"] == "COMPLETED"
    assert result["section_status"]["spot_futures_basis"] == "COMPLETED"


def test_required_database_url_fails_startup_when_missing(monkeypatch):
    import asyncio
    from app.main import lifespan

    monkeypatch.setattr(settings, "require_database_url", True)
    monkeypatch.setattr(settings, "database_url", "   ")

    async def run_lifespan():
        async with lifespan(app):
            pass

    try:
        asyncio.run(run_lifespan())
    except RuntimeError as exc:
        assert "DATABASE_URL is required" in str(exc)
    else:
        raise AssertionError("Production startup must fail without DATABASE_URL")


def test_dashboard_markup_has_no_literal_newline_separator():
    from pathlib import Path
    dashboard = Path(__file__).resolve().parents[1] / "dashboard" / "index.html"
    html = dashboard.read_text(encoding="utf-8")
    assert r"</div>\n<div>" not in html


def test_production_rejects_weak_client_key_even_with_strong_owner_key(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "personal_api_key", "test-owner-key-with-enough-entropy")
    monkeypatch.setattr(settings, "ai_client_api_keys", '{"chatgpt":"weak-client-key"}')
    response = client.get(
        "/api/v1/analysis/futures/liquidations/status",
        headers={"Authorization": "Bearer test-owner-key-with-enough-entropy"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"


def test_private_api_rejects_unauthenticated_write_and_collection_endpoints(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", "test-owner-key-with-enough-entropy")
    monkeypatch.setattr(settings, "ai_client_api_keys", "{}")
    requests = [
        client.post(
            "/api/v1/history/market-confluence/snapshots",
            json={"status": "COMPLETED"},
        ),
        client.post(
            "/api/v1/history/funding-rates/USD_M/BTCUSDT/collect",
            params={"limit": 1},
        ),
        client.post(
            "/api/v1/history/open-interest/USD_M/BTCUSDT/collect",
            params={"limit": 1},
        ),
        client.post(
            "/api/v1/history/derivatives-ratios/USD_M/global_long_short_account/BTCUSDT/collect",
            params={"limit": 1},
        ),
        client.post(
            "/api/v1/history/klines/SPOT/BTCUSDT/collect",
            params={"interval": "1h", "limit": 1},
        ),
        client.post(
            "/api/v1/onchain/evm/token/0x1111111111111111111111111111111111111111/index",
            json={"from_block": 1, "to_block": 2},
        ),
    ]
    assert [response.status_code for response in requests] == [401] * 6
    assert all(response.json()["error"]["code"] == "UNAUTHORIZED" for response in requests)


def test_malformed_client_key_configuration_fails_closed_without_owner_key(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", "")
    monkeypatch.setattr(settings, "ai_client_api_keys", '{"chatgpt":')
    response = client.get("/api/v1/analysis/futures/liquidations/status")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"


def test_owner_and_client_key_collision_is_rejected_as_ambiguous(monkeypatch):
    shared_key = "shared-owner-client-key-12345678901234567890"
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "personal_api_key", shared_key)
    monkeypatch.setattr(
        settings,
        "ai_client_api_keys",
        json.dumps({"chatgpt": shared_key}),
    )
    response = client.get(
        "/api/v1/analysis/futures/liquidations/status",
        headers={"Authorization": f"Bearer {shared_key}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
