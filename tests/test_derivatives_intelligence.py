from app.services.derivatives_intelligence import (
    get_derivatives_intelligence,
    summarize_order_book,
)


def test_order_book_spread_and_depth_imbalance():
    result = summarize_order_book({
        "bids": [["99", "2"], ["98", "1"]],
        "asks": [["101", "1"], ["102", "1"]],
    }, levels=2)
    assert result["status"] == "COMPLETED"
    assert result["best_bid"] == 99.0
    assert result["best_ask"] == 101.0
    assert result["spread"] == 2.0
    assert result["bid_notional"] > result["ask_notional"]
    assert result["depth_imbalance"] > 0


def test_order_book_empty_side_is_incomplete():
    result = summarize_order_book({"bids": [], "asks": []})
    assert result["status"] == "INCOMPLETE"
    assert result["spread_bps"] is None


class FakeProvider:
    market = "USD_M"

    async def funding_rate(self, symbol, limit):
        return [{"symbol": symbol, "fundingRate": "0.0001", "fundingTime": 1000}]

    async def open_interest(self, symbol):
        return {"symbol": symbol, "openInterest": "123.4", "time": 1000}

    async def open_interest_history(self, symbol, period, limit):
        return [{"symbol": symbol, "sumOpenInterest": "120", "timestamp": 900}]

    async def global_long_short_ratio(self, symbol, period, limit):
        return [{"symbol": symbol, "longShortRatio": "1.2", "timestamp": 900}]

    async def taker_long_short_ratio(self, symbol, period, limit):
        return [{"buySellRatio": "1.1", "buyVol": "11", "sellVol": "10", "timestamp": 900}]

    async def order_book(self, symbol, limit):
        return {
            "lastUpdateId": 7,
            "E": 1000,
            "T": 999,
            "bids": [["99", "2"]],
            "asks": [["101", "1"]],
        }


async def test_derivatives_intelligence_aggregates_public_sections():
    result = await get_derivatives_intelligence(FakeProvider(), "btcusdt")
    assert result["status"] == "COMPLETED"
    assert result["symbol"] == "BTCUSDT"
    assert result["sections"]["open_interest"]["data"]["openInterest"] == "123.4"
    assert result["sections"]["order_book"]["data"]["spread"] == 2.0


def test_order_book_rejects_non_finite_and_non_positive_levels():
    result = summarize_order_book({
        "bids": [["nan", "2"], ["99", "0"], ["98", "1"]],
        "asks": [["101", "inf"], ["102", "1"]],
    }, levels=3)
    assert result["status"] == "COMPLETED"
    assert result["best_bid"] == 98.0
    assert result["best_ask"] == 102.0
    assert result["bid_levels_received"] == 1
    assert result["ask_levels_received"] == 1


def test_order_book_with_crossed_prices_is_incomplete():
    result = summarize_order_book({
        "bids": [["102", "1"]],
        "asks": [["101", "2"]],
    })
    assert result["status"] == "INCOMPLETE"
    assert result["spread"] is None
    assert result["depth_imbalance"] is None


def test_order_book_ignores_malformed_rows():
    result = summarize_order_book({
        "bids": [None, ["99"], ["99", "2"]],
        "asks": ["bad", ["101", "1"]],
    })
    assert result["status"] == "COMPLETED"
    assert result["bid_levels_received"] == 1
    assert result["ask_levels_received"] == 1


class FailingProvider(FakeProvider):
    async def open_interest(self, symbol):
        raise RuntimeError("https://futures.example/api?secret=do-not-leak")


async def test_derivatives_intelligence_sanitizes_upstream_error():
    result = await get_derivatives_intelligence(FailingProvider(), "btcusdt")
    section = result["sections"]["open_interest"]
    assert result["status"] == "INCOMPLETE"
    assert section["error"] == "UPSTREAM_UNAVAILABLE"
    assert "do-not-leak" not in str(result)
