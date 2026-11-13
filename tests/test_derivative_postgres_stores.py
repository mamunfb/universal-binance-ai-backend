from app.services.funding_rates import FundingRateStore
from app.services.open_interest import OpenInterestStore


class FakePostgresConnection:
    def __init__(self, history_row):
        self.history_row = history_row
        self.executemany_calls = []
        self.execute_calls = []
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self

    def executemany(self, query, values):
        self.executemany_calls.append((query, values))

    def execute(self, query, params):
        self.execute_calls.append((query, params))
        if "COUNT(*)" in query:
            self.result = {"count": 1}
        else:
            self.result = [self.history_row]
        return self

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


def test_funding_store_postgres_save_and_history_are_parameterized(monkeypatch):
    from app.services import funding_rates as module

    row = {
        "funding_time_ms": 1_700_000_000_000,
        "funding_rate": 0.0001,
        "mark_price": 37000.0,
        "source": "test",
        "collected_at": "2026-01-01T00:00:00+00:00",
    }
    connection = FakePostgresConnection(row)
    monkeypatch.setattr(module.psycopg, "connect", lambda *_a, **_kw: connection)
    store = FundingRateStore("unused.sqlite3", "postgresql://example.invalid/db")

    saved = store.save("USD_M", "BTCUSDT", [{
        "symbol": "BTCUSDT", "fundingTime": 1_700_000_000_000,
        "fundingRate": "0.0001", "markPrice": "37000",
    }])
    history = store.history(
        "USD_M", "BTCUSDT", start_time_ms=1_699_999_000_000,
        end_time_ms=1_700_001_000_000,
    )

    insert_sql, insert_values = connection.executemany_calls[0]
    select_sql, select_values = connection.execute_calls[1]
    assert saved["storage"] == "POSTGRESQL"
    assert saved["total_stored_count"] == 1
    assert insert_sql.count("%s") == 7
    assert len(insert_values[0]) == 7
    assert "ON CONFLICT(market, symbol, funding_time_ms)" in insert_sql
    assert history["returned_count"] == 1
    assert "funding_time_ms>=%s" in select_sql
    assert "funding_time_ms<=%s" in select_sql
    assert "ORDER BY funding_time_ms DESC LIMIT %s" in select_sql
    assert select_values == (
        "USD_M", "BTCUSDT", 1_699_999_000_000, 1_700_001_000_000, 1000,
    )


def test_open_interest_store_postgres_save_and_history_are_parameterized(monkeypatch):
    from app.services import open_interest as module

    row = {
        "timestamp_ms": 1_700_000_000_000,
        "sum_open_interest": 123.45,
        "sum_open_interest_value": 4567890.12,
        "cmc_circulating_supply": 19000000.0,
        "source": "test",
        "collected_at": "2026-01-01T00:00:00+00:00",
    }
    connection = FakePostgresConnection(row)
    monkeypatch.setattr(module.psycopg, "connect", lambda *_a, **_kw: connection)
    store = OpenInterestStore("unused.sqlite3", "postgresql://example.invalid/db")

    saved = store.save("USD_M", "BTCUSDT", "1h", [{
        "symbol": "BTCUSDT", "timestamp": 1_700_000_000_000,
        "sumOpenInterest": "123.45", "sumOpenInterestValue": "4567890.12",
        "CMCCirculatingSupply": "19000000",
    }])
    history = store.history(
        "USD_M", "BTCUSDT", "1h",
        start_time_ms=1_699_999_000_000, end_time_ms=1_700_001_000_000,
    )

    insert_sql, insert_values = connection.executemany_calls[0]
    select_sql, select_values = connection.execute_calls[1]
    assert saved["storage"] == "POSTGRESQL"
    assert saved["total_stored_count"] == 1
    assert insert_sql.count("%s") == 9
    assert len(insert_values[0]) == 9
    assert "ON CONFLICT(market, symbol, period, timestamp_ms)" in insert_sql
    assert history["returned_count"] == 1
    assert "timestamp_ms>=%s" in select_sql
    assert "timestamp_ms<=%s" in select_sql
    assert "ORDER BY timestamp_ms DESC LIMIT %s" in select_sql
    assert select_values == (
        "USD_M", "BTCUSDT", "1h", 1_699_999_000_000, 1_700_001_000_000, 500,
    )
