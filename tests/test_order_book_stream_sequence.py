import pytest

from app.services.order_book_stream import OrderBookStreamCollector


@pytest.mark.parametrize("market", ["SPOT", "USD_M", "COIN_M"])
def test_initial_depth_event_must_bridge_snapshot(market):
    OrderBookStreamCollector._validate_sequence(
        market, {"U": 10, "u": 12}, last_id=11, first_event=True
    )
    with pytest.raises(RuntimeError):
        OrderBookStreamCollector._validate_sequence(
            market, {"U": 13, "u": 14}, last_id=11, first_event=True
        )


def test_spot_depth_gap_detection():
    OrderBookStreamCollector._validate_sequence(
        "SPOT", {"U": 12, "u": 13}, last_id=11, first_event=False
    )
    with pytest.raises(RuntimeError):
        OrderBookStreamCollector._validate_sequence(
            "SPOT", {"U": 13, "u": 14}, last_id=11, first_event=False
        )


@pytest.mark.parametrize("market", ["USD_M", "COIN_M"])
def test_futures_depth_requires_previous_update_id(market):
    OrderBookStreamCollector._validate_sequence(
        market, {"U": 12, "u": 13, "pu": 11}, last_id=11, first_event=False
    )
    with pytest.raises(RuntimeError):
        OrderBookStreamCollector._validate_sequence(
            market, {"U": 12, "u": 13, "pu": 10}, last_id=11, first_event=False
        )
