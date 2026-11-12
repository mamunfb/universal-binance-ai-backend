from app.services.market_confluence_store import MarketConfluenceStore

def test_snapshot_save_is_idempotent(tmp_path):
    store=MarketConfluenceStore(str(tmp_path/"snapshots.sqlite3"))
    payload={"market":"USD_M","symbol":"BTCUSDT","interval":"1h","analyzed_at_ms":1000,
        "confluence":{"bias":"BULLISH","alignment":"BULLISH_EVIDENCE_ALIGNMENT"},
        "reference":{"price":100.0,"close_time_ms":999},"evidence":[{"source":"TEST"}]}
    a=store.save(payload); b=store.save(payload)
    assert a["snapshot_id"]==b["snapshot_id"]
    assert store.history("USD_M","BTCUSDT","1h")["returned_count"]==1


def test_future_reference_candle_is_rejected(tmp_path):
    store=MarketConfluenceStore(str(tmp_path/"snapshots.sqlite3"))
    payload={"market":"USD_M","symbol":"BTCUSDT","interval":"1h","analyzed_at_ms":1000,
        "confluence":{"bias":"BULLISH","alignment":"BULLISH_EVIDENCE_ALIGNMENT"},
        "reference":{"price":100.0,"close_time_ms":1001}}
    try:
        store.save(payload)
    except ValueError as exc:
        assert "fully closed" in str(exc)
    else:
        raise AssertionError("future reference candle must be rejected")


def test_snapshot_store_uses_postgres_when_database_url_is_configured(tmp_path, monkeypatch):
    store = MarketConfluenceStore(str(tmp_path / "unused.sqlite3"), "postgresql://example.invalid/db")
    assert store.database_url.startswith("postgresql://")
    assert not (tmp_path / "unused.sqlite3").exists()


def test_snapshot_validation_is_shared_by_both_storage_modes(tmp_path):
    store = MarketConfluenceStore(str(tmp_path / "snapshots.sqlite3"))
    payload = {"market": "USD_M", "symbol": "BTCUSDT", "interval": "1h", "analyzed_at_ms": 1000,
               "confluence": {"bias": "BULLISH"}, "reference": {"price": 100, "close_time_ms": 999}}
    result = store.save(payload)
    assert result["bias"] == "BULLISH"
    assert store.get_snapshot("USD_M", "BTCUSDT", result["snapshot_id"])["payload"] == payload
