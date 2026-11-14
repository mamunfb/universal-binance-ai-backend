import os
from uuid import uuid4

import psycopg
import pytest

from app.providers.evm_rpc import TRANSFER_TOPIC
from app.services.aggregate_trade_stream import AggregateTradeStore
from app.services.collector_lease import CollectorLeaseLostError, PostgresCollectorLease
from app.services.derivatives_ratio_store import DerivativesRatioStore
from app.services.funding_rates import FundingRateStore
from app.services.historical_klines import HistoricalKlineStore
from app.services.open_interest import OpenInterestStore
from app.services.evm_transfer_store import EVMTransferStore


DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration verification",
)


def _topic(address: str) -> str:
    return "0x" + address[2:].rjust(64, "0")


def test_postgres_derivatives_ratio_write_is_fenced_by_lease():
    suffix = uuid4().hex[:10].upper()
    symbol = f"TEST{suffix}"
    lease_name = f"test-derivatives-ratio:{suffix}"
    manager = PostgresCollectorLease(DATABASE_URL, lease_name, ttl_seconds=30)
    lease = manager.acquire()
    assert lease is not None
    store = DerivativesRatioStore("unused.sqlite3", DATABASE_URL)
    timestamp = 1_800_000_000_000
    try:
        result = store.save(
            "GLOBAL_LONG_SHORT",
            symbol,
            "1h",
            [{
                "symbol": symbol,
                "timestamp": timestamp,
                "longShortRatio": "1.2",
                "longAccount": "0.55",
                "shortAccount": "0.45",
            }],
            source="PostgreSQL lease integration test",
            lease=lease,
        )
        assert result["storage"] == "POSTGRESQL"
        history = store.history("GLOBAL_LONG_SHORT", symbol, "1h")
        assert history["returned_count"] == 1
        assert history["records"][0]["long_short_ratio"] == 1.2
        manager.release(lease)
        with pytest.raises(CollectorLeaseLostError):
            store.save(
                "GLOBAL_LONG_SHORT", symbol, "1h",
                [{
                    "symbol": symbol, "timestamp": timestamp + 3_600_000,
                    "longShortRatio": "1.3", "longAccount": "0.56", "shortAccount": "0.44",
                }],
                lease=lease,
            )
    finally:
        manager.release(lease)
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM public.derivatives_ratio_history WHERE symbol=%s",
                (symbol,),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=%s",
                (lease_name,),
            )


def test_postgres_evm_chunk_and_coverage_are_written_under_same_lease():
    suffix = (uuid4().hex + uuid4().hex[:8])
    contract = "0x" + suffix
    sender = "0x" + "1" * 40
    recipient = "0x" + "2" * 40
    transaction_hash = "0x" + uuid4().hex * 2
    lease_name = f"test-evm-transfer:1:{contract}"
    manager = PostgresCollectorLease(DATABASE_URL, lease_name, ttl_seconds=30)
    lease = manager.acquire()
    assert lease is not None
    store = EVMTransferStore("unused.sqlite3", DATABASE_URL)
    log = {
        "topics": [TRANSFER_TOPIC, _topic(sender), _topic(recipient)],
        "data": hex(12345),
        "transactionHash": transaction_hash,
        "blockNumber": "0x64",
        "logIndex": "0x0",
    }
    try:
        assert store.save_chunk(1, contract, 100, 110, [log], lease=lease) == 1
        rows = store.history(1, contract, 100, 110)
        assert len(rows) == 1
        assert rows[0]["amount_raw"] == "12345"
        coverage = store.coverage(1, contract)
        assert len(coverage) == 1
        assert coverage[0]["from_block"] == 100
        assert coverage[0]["to_block"] == 110
        manager.release(lease)
        with pytest.raises(CollectorLeaseLostError):
            store.save_chunk(1, contract, 111, 111, [], lease=lease)
        assert len(store.coverage(1, contract)) == 1
    finally:
        manager.release(lease)
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM public.evm_transfer_logs WHERE chain_id=1 AND contract_address=%s",
                (contract,),
            )
            connection.execute(
                "DELETE FROM public.evm_transfer_index_ranges WHERE chain_id=1 AND contract_address=%s",
                (contract,),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=%s",
                (lease_name,),
            )



def test_postgres_aggregate_trade_write_is_fenced_by_lease():
    suffix = uuid4().hex[:10].upper()
    symbol = f"TEST{suffix}"
    lease_name = f"aggregate-trade:SPOT:{symbol}"
    manager = PostgresCollectorLease(DATABASE_URL, lease_name, ttl_seconds=30)
    lease = manager.acquire()
    assert lease is not None
    store = AggregateTradeStore("unused.sqlite3", DATABASE_URL)
    row = {
        "market": "SPOT",
        "symbol": symbol,
        "trade_id": 1,
        "event_time_ms": 1_800_000_000_000,
        "trade_time_ms": 1_800_000_000_000,
        "price": 100.0,
        "quantity": 0.25,
        "notional": 25.0,
        "buyer_is_maker": False,
        "aggressor_side": "BUY",
        "raw_json": '{"e":"aggTrade","s":"' + symbol + '","a":1}',
    }
    try:
        store.insert(row, lease=lease)
        rows = store.recent("SPOT", symbol, limit=10)
        assert len(rows) == 1
        assert rows[0]["trade_id"] == 1
        assert rows[0]["buyer_is_maker"] is False
        manager.release(lease)
        stale_row = {**row, "trade_id": 2, "event_time_ms": row["event_time_ms"] + 1,
                     "trade_time_ms": row["trade_time_ms"] + 1}
        with pytest.raises(CollectorLeaseLostError):
            store.insert(stale_row, lease=lease)
        assert store.count("SPOT", symbol) == 1
    finally:
        manager.release(lease)
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM public.aggregate_trades WHERE market=%s AND symbol=%s",
                ("SPOT", symbol),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=%s",
                (lease_name,),
            )


def test_postgres_lease_share_lock_blocks_expired_lease_takeover():
    suffix = uuid4().hex[:12]
    lease_name = f"test-lease-share-lock:{suffix}"
    owner = PostgresCollectorLease(DATABASE_URL, lease_name, ttl_seconds=30)
    lease = owner.acquire()
    assert lease is not None
    contender = PostgresCollectorLease(
        DATABASE_URL, lease_name, owner_id=uuid4(), ttl_seconds=30,
    )
    replacement = None
    try:
        # The protected writer holds FOR SHARE in its transaction. Even an
        # attempted takeover-style UPDATE must wait for that transaction.
        with psycopg.connect(DATABASE_URL) as writer_connection:
            assert PostgresCollectorLease.lock_if_owned(writer_connection, lease)
            with psycopg.connect(DATABASE_URL) as takeover_connection:
                takeover_connection.execute("SET LOCAL lock_timeout = '250ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    takeover_connection.execute(
                        """
                        UPDATE public.collector_leases
                           SET lease_expires_at = clock_timestamp() - INTERVAL '1 second'
                         WHERE lease_name = %s
                        """,
                        (lease_name,),
                    )
                takeover_connection.rollback()

        # Once the protected transaction commits, an expired lease can be
        # taken over, and the fencing token must advance for the new owner.
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                """
                UPDATE public.collector_leases
                   SET lease_expires_at = clock_timestamp() - INTERVAL '1 second'
                 WHERE lease_name = %s
                """,
                (lease_name,),
            )
        replacement = contender.acquire()
        assert replacement is not None
        assert replacement.owner_id == contender.owner_id
        assert replacement.fencing_token == lease.fencing_token + 1
        with psycopg.connect(DATABASE_URL) as stale_writer_connection:
            assert not PostgresCollectorLease.lock_if_owned(
                stale_writer_connection, lease
            )
    finally:
        if replacement is not None:
            contender.release(replacement)
        owner.release(lease)
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=%s",
                (lease_name,),
            )


def test_postgres_release_rejects_stale_lease_snapshot_after_renewal():
    suffix = uuid4().hex[:12]
    lease_name = f"test-lease-stale-release:{suffix}"
    manager = PostgresCollectorLease(DATABASE_URL, lease_name, ttl_seconds=30)
    lease = manager.acquire()
    assert lease is not None
    renewed = None
    try:
        renewed = manager.renew(lease)
        assert renewed is not None
        assert renewed.fencing_token == lease.fencing_token
        assert renewed.lease_expires_at > lease.lease_expires_at

        # A delayed cleanup holding the pre-renewal snapshot must not expire
        # the currently renewed lease owned by this same collector.
        assert manager.release(lease) is False
        with psycopg.connect(DATABASE_URL) as connection:
            assert PostgresCollectorLease.lock_if_owned(connection, renewed)

        assert manager.release(renewed) is True
        with psycopg.connect(DATABASE_URL) as connection:
            assert not PostgresCollectorLease.lock_if_owned(connection, renewed)
    finally:
        if renewed is not None:
            manager.release(renewed)
        else:
            manager.release(lease)
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=%s",
                (lease_name,),
            )


def test_postgres_funding_rate_write_rejects_released_lease():
    suffix = uuid4().hex[:10].upper()
    symbol = f"TEST{suffix}"
    lease_name = f"test-funding-fence:{suffix}"
    manager = PostgresCollectorLease(DATABASE_URL, lease_name, ttl_seconds=30)
    lease = manager.acquire()
    assert lease is not None
    store = FundingRateStore("unused.sqlite3", DATABASE_URL)
    row = {"symbol": symbol, "fundingTime": 1_800_000_000_000, "fundingRate": "0.001", "markPrice": "100"}
    try:
        result = store.save("USD_M", symbol, [row], lease=lease)
        assert result["storage"] == "POSTGRESQL"
        assert store.history("USD_M", symbol)["returned_count"] == 1
        assert manager.release(lease) is True
        stale = {**row, "fundingTime": row["fundingTime"] + 28_800_000}
        with pytest.raises(CollectorLeaseLostError):
            store.save("USD_M", symbol, [stale], lease=lease)
        assert store.history("USD_M", symbol)["returned_count"] == 1
    finally:
        manager.release(lease)
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM public.historical_funding_rates WHERE market=%s AND symbol=%s",
                ("USD_M", symbol),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=%s", (lease_name,)
            )


def test_postgres_open_interest_write_rejects_released_lease():
    suffix = uuid4().hex[:10].upper()
    symbol = f"TEST{suffix}"
    lease_name = f"test-open-interest-fence:{suffix}"
    manager = PostgresCollectorLease(DATABASE_URL, lease_name, ttl_seconds=30)
    lease = manager.acquire()
    assert lease is not None
    store = OpenInterestStore("unused.sqlite3", DATABASE_URL)
    row = {
        "symbol": symbol, "timestamp": 1_800_000_000_000,
        "sumOpenInterest": "12.5", "sumOpenInterestValue": "1250",
    }
    try:
        result = store.save("USD_M", symbol, "1h", [row], lease=lease)
        assert result["storage"] == "POSTGRESQL"
        assert store.history("USD_M", symbol, "1h")["returned_count"] == 1
        assert manager.release(lease) is True
        stale = {**row, "timestamp": row["timestamp"] + 3_600_000}
        with pytest.raises(CollectorLeaseLostError):
            store.save("USD_M", symbol, "1h", [stale], lease=lease)
        assert store.history("USD_M", symbol, "1h")["returned_count"] == 1
    finally:
        manager.release(lease)
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM public.historical_open_interest WHERE market=%s AND symbol=%s",
                ("USD_M", symbol),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=%s", (lease_name,)
            )


def test_postgres_historical_kline_write_rejects_released_lease():
    suffix = uuid4().hex[:10].upper()
    symbol = f"TEST{suffix}"
    lease_name = f"test-historical-kline-fence:{suffix}"
    manager = PostgresCollectorLease(DATABASE_URL, lease_name, ttl_seconds=30)
    lease = manager.acquire()
    assert lease is not None
    store = HistoricalKlineStore("unused.sqlite3", DATABASE_URL)
    open_time = 1_800_000_000_000
    row = [
        open_time, "100", "105", "99", "102", "10",
        open_time + 59_999, "1020", 5, "4", "408", "0",
    ]
    try:
        result = store.save_klines("SPOT", symbol, "1m", [row], lease=lease)
        assert result["storage"] == "POSTGRESQL"
        assert store.history("SPOT", symbol, "1m")["returned_count"] == 1
        assert manager.release(lease) is True
        stale = list(row)
        stale[0] += 60_000
        stale[6] += 60_000
        with pytest.raises(CollectorLeaseLostError):
            store.save_klines("SPOT", symbol, "1m", [stale], lease=lease)
        assert store.history("SPOT", symbol, "1m")["returned_count"] == 1
    finally:
        manager.release(lease)
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM public.historical_klines WHERE market=%s AND symbol=%s AND interval=%s",
                ("SPOT", symbol, "1m"),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=%s", (lease_name,)
            )
