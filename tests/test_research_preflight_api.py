from fastapi.testclient import TestClient

from app import main
from app.main import app


client = TestClient(app)


def test_research_preflight_reports_live_market_probes_and_capability_limits(monkeypatch):
    class FakeProvider:
        async def exchange_info(self):
            return {"symbols": [{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}]}

    monkeypatch.setattr(main, "get_spot_provider", lambda: FakeProvider())
    monkeypatch.setattr(main, "get_futures_provider", lambda market: FakeProvider())
    monkeypatch.setattr(main.settings, "news_rss_feeds", "Example=https://example.com/feed.xml")
    monkeypatch.setattr(main.settings, "evm_rpc_url", "")
    monkeypatch.setattr(main.settings, "evm_chain_rpc_urls", "[]")

    response = client.get("/api/v1/research/preflight")
    assert response.status_code == 200
    payload = response.json()
    assert payload["capabilities"]["binance_live_market_data"] == "AVAILABLE"
    assert payload["market_data"]["spot"]["symbol_count"] == 2
    assert payload["capabilities"]["news_sources"] == "CONFIGURED"
    assert payload["capabilities"]["live_web_search"] == "NOT_ASSESSABLE_BY_BACKEND"
    assert payload["capabilities"]["onchain_provider"] == "UNAVAILABLE"
    assert payload["trading_enabled"] is False
    assert payload["api_credentials_required"] is False


def test_research_preflight_marks_unreachable_binance_market_partial(monkeypatch):
    class GoodProvider:
        async def exchange_info(self):
            return {"symbols": [{"symbol": "BTCUSDT"}]}

    class FailedProvider:
        async def exchange_info(self):
            raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(main, "get_spot_provider", lambda: GoodProvider())
    monkeypatch.setattr(
        main, "get_futures_provider",
        lambda market: GoodProvider() if market == "USD_M" else FailedProvider(),
    )
    monkeypatch.setattr(main.settings, "news_rss_feeds", "")
    monkeypatch.setattr(main.settings, "evm_rpc_url", "")
    monkeypatch.setattr(main.settings, "evm_chain_rpc_urls", "[]")

    response = client.get("/api/v1/research/preflight")
    assert response.status_code == 200
    payload = response.json()
    assert payload["capabilities"]["binance_live_market_data"] == "PARTIAL"
    assert payload["market_data"]["coinm"]["status"] == "UNAVAILABLE"
    assert payload["capabilities"]["news_sources"] == "UNAVAILABLE"
