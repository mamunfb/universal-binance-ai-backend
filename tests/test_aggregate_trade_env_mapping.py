import pytest

from app.config import Settings


def test_aggregate_trade_jobs_uses_canonical_environment_variable(monkeypatch):
    monkeypatch.setenv(
        "AGGREGATE_TRADE_COLLECTOR_JOBS",
        '[{"market":"USD_M","symbol":"BTCUSDT"}]',
    )
    monkeypatch.delenv("AGG_TRADE_COLLECTOR_JOBS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.aggregate_trade_collector_jobs == (
        '[{"market":"USD_M","symbol":"BTCUSDT"}]'
    )


def test_legacy_short_aggregate_trade_jobs_name_is_not_required(monkeypatch):
    monkeypatch.delenv("AGGREGATE_TRADE_COLLECTOR_JOBS", raising=False)
    monkeypatch.setenv("AGG_TRADE_COLLECTOR_JOBS", '[{"market":"SPOT","symbol":"ETHUSDT"}]')

    settings = Settings(_env_file=None)

    assert settings.aggregate_trade_collector_jobs == "[]"
