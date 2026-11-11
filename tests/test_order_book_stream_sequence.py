import pytest

from app.services.order_book_stream import OrderBookStreamCollector


@pytest.mark.parametrize("market", ["SPOT", "USD_M", "COIN_M"])
def test_initial_depth_event_must_bridge_snapshot(market):
    valid_event = {"U": 10, "u": 12}
    invalid_event = {"U": 13, "u": 14}
    if market in {"USD_M", "COIN_M"}:
        # Futures streams include pu even when the first event overlaps the snapshot.
        valid_event["pu"] = 9
        invalid_event["pu"] = 12
    OrderBookStreamCollector._validate_sequence(
        market, valid_event, last_id=11, first_event=True
    )
    with pytest.raises(RuntimeError):
        OrderBookStreamCollector._validate_sequence(
            market, invalid_event, last_id=11, first_event=True
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
