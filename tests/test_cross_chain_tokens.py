import asyncio

import pytest

from app.services.cross_chain_tokens import parse_chain_token_configs, cross_chain_erc20_snapshot

ADDRESS = "0x" + "1" * 40
CONTRACT = "0x" + "2" * 40


def test_parse_chain_token_configs_validates_contracts_and_duplicates():
    raw = '[{"chain_id":1,"asset_id":"usd-coin","contract_address":"' + CONTRACT + '","rpc_url":"https://rpc.example"}]'
    parsed = parse_chain_token_configs(raw)
    assert parsed[0]["asset_id"] == "usd-coin"
    with pytest.raises(ValueError, match="HTTPS"):
        parse_chain_token_configs(raw.replace("https://", "http://"))
    with pytest.raises(ValueError, match="Duplicate"):
        parse_chain_token_configs(raw[:-1] + ',' + raw[1:])


def test_cross_chain_erc20_snapshot_pins_calls_to_observed_block(monkeypatch):
    calls = []

    class FakeProvider:
        def __init__(self, url, timeout):
            self.url = url
        async def chain_id(self):
            return 1
        async def block_number(self):
            return 123
        async def block_timestamp(self, block_number):
            assert block_number == 123
            return 1700000000
        async def eth_call(self, contract, data, block="latest"):
            calls.append((data[:10], block))
            if data == "0x18160ddd":
                return "0x" + (1000).to_bytes(32, "big").hex()
            if data == "0x313ce567":
                return "0x" + (2).to_bytes(32, "big").hex()
            if data in ("0x95d89b41", "0x06fdde03"):
                return "0x" + (64).to_bytes(32, "big").hex() + (3).to_bytes(32, "big").hex() + "555344" + "00" * 29
            return "0x" + (250).to_bytes(32, "big").hex()

    monkeypatch.setattr("app.services.cross_chain_tokens.EVMRPCProvider", FakeProvider)
    config = [{"chain_id": 1, "asset_id": "usd-coin", "contract_address": CONTRACT,
               "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}]
    result = asyncio.run(cross_chain_erc20_snapshot(config, "usd-coin", [ADDRESS]))
    assert result["status"] == "COMPLETED"
    assert result["chains"][0]["snapshot_block"] == 123
    assert result["chains"][0]["snapshot_block_number"] == 123
    assert result["chains"][0]["snapshot_block_timestamp"] == 1700000000
    assert result["chains"][0]["snapshot_timestamp_status"] == "AVAILABLE"
    assert result["chains"][0]["snapshot_block_time"] is not None
    assert result["chains"][0]["snapshot_age_seconds"] >= 0
    assert result["chains"][0]["wallets"][0]["balance_tokens"] == 2.5
    assert calls and all(block == "0x7b" for _, block in calls)


def test_cross_chain_erc20_rejects_unknown_asset_and_bad_address():
    with pytest.raises(ValueError, match="No configured"):
        asyncio.run(cross_chain_erc20_snapshot([], "unknown", [ADDRESS]))
    with pytest.raises(ValueError, match="EVM address"):
        asyncio.run(cross_chain_erc20_snapshot(
            [{"chain_id": 1, "asset_id": "x", "contract_address": CONTRACT,
              "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}],
            "x", ["bad"]))


def test_cross_chain_token_uint_decoder_rejects_malformed_words():
    from app.services.cross_chain_tokens import _uint
    for value in ("0x1", "0x" + "00" * 31, "0x" + "zz" * 32):
        with pytest.raises(ValueError):
            _uint(value)
    assert _uint("0x" + (123).to_bytes(32, "big").hex()) == 123


def test_cross_chain_token_text_decoder_supports_bytes32_and_rejects_bad_offsets():
    from app.services.cross_chain_tokens import _text
    assert _text("0x" + b"USDC".ljust(32, b"\\x00").hex()) == "USDC"
    malformed = "0x" + (32).to_bytes(32, "big").hex() + (999).to_bytes(32, "big").hex()
    assert _text(malformed) is None


def test_parse_chain_token_configs_caps_entries():
    raw = '[{"chain_id":1,"asset_id":"asset-' + 'a' + '","contract_address":"' + CONTRACT + '","rpc_url":"https://rpc.example"}]'
    entry = raw[1:-1]
    with pytest.raises(ValueError, match="20"):
        parse_chain_token_configs("[" + ",".join([entry] * 21) + "]")


def test_cross_chain_token_snapshot_sanitizes_provider_errors(monkeypatch):
    class FakeProvider:
        def __init__(self, url, timeout):
            pass
        async def chain_id(self):
            raise RuntimeError("https://rpc.example/key=secret-token")

    monkeypatch.setattr("app.services.cross_chain_tokens.EVMRPCProvider", FakeProvider)
    config = [{"chain_id": 1, "asset_id": "usd-coin", "contract_address": CONTRACT,
               "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}]
    result = asyncio.run(cross_chain_erc20_snapshot(config, "usd-coin", [ADDRESS]))
    assert result["status"] == "INCOMPLETE"
    assert result["chains"][0]["error"] == "CHAIN_SNAPSHOT_UNAVAILABLE"
    assert "secret-token" not in str(result)
