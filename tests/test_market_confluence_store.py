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


def test_postgres_adapter_save_history_and_get_snapshot(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from app.services import market_confluence_store as module

    rows = {}

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params):
            if query.lstrip().startswith("INSERT INTO"):
                key = (params[1], params[2], params[3], params[4])
                rows.setdefault(key, {
                    "snapshot_id": params[0], "market": params[1], "symbol": params[2],
                    "interval": params[3], "analyzed_at_ms": params[4], "bias": params[5],
                    "alignment": params[6], "reference_price": params[7],
                    "reference_close_time_ms": params[8], "payload": params[9].obj,
                    "created_at": datetime.now(timezone.utc),
                })
                return self
            if "WHERE market=%s AND symbol=%s AND interval=%s AND analyzed_at_ms=%s" in query:
                self.result = {"snapshot_id": rows[(params[0], params[1], params[2], params[3])]["snapshot_id"]}
                return self
            if "ORDER BY analyzed_at_ms DESC LIMIT" in query:
                found = [v for k, v in rows.items() if k[:3] == params[:3]]
                self.results = sorted(found, key=lambda x: x["analyzed_at_ms"], reverse=True)[:params[3]]
                return self
            if "WHERE snapshot_id=%s AND market=%s AND symbol=%s" in query:
                self.result = next((v for v in rows.values() if
                    (v["snapshot_id"], v["market"], v["symbol"]) == params), None)
                return self
            raise AssertionError(f"Unexpected SQL: {query}")

        def fetchone(self):
            return getattr(self, "result", None)

        def fetchall(self):
            return getattr(self, "results", [])

    monkeypatch.setattr(module.psycopg, "connect", lambda *_a, **_kw: FakeConnection())
    store = MarketConfluenceStore(str(tmp_path / "unused.sqlite3"), "postgresql://example.invalid/db")
    payload = {
        "market": "USD_M", "symbol": "BTCUSDT", "interval": "1h", "analyzed_at_ms": 1000,
        "confluence": {"bias": "BULLISH", "alignment": "BULLISH_EVIDENCE_ALIGNMENT"},
        "reference": {"price": 100.0, "close_time_ms": 999}, "evidence": [],
    }

    saved = store.save(payload)
    snapshot = store.get_snapshot("USD_M", "BTCUSDT", saved["snapshot_id"])
    history = store.history("USD_M", "BTCUSDT", "1h")

    assert saved["status"] == "STORED"
    assert snapshot["payload"] == payload
    assert history["returned_count"] == 1
    assert history["source"] == "Neon PostgreSQL confluence snapshot store"
    assert not (tmp_path / "unused.sqlite3").exists()
