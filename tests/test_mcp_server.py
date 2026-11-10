"""Contract tests for the private MCP adapter."""
import importlib
import os
import sys

import pytest

MODULE = "mcp_server.server"


def _load_server(monkeypatch, client_name="chatgpt", base_url="https://api.example.test"):
    keys = {
        name: f"{name}-" + ("x" * 40)
        for name in ("chatgpt", "gemini", "manus", "claude", "perplexity")
    }
    monkeypatch.setenv("PERSONAL_API_BASE_URL", base_url)
    monkeypatch.setenv("MCP_CLIENT_NAME", client_name)
    monkeypatch.setenv("AI_CLIENT_API_KEYS", __import__("json").dumps(keys))
    monkeypatch.setenv("APP_ENV", "production")
    sys.modules.pop(MODULE, None)
    return importlib.import_module(MODULE)


def test_mcp_registers_only_read_only_tool_surface(monkeypatch):
    server = _load_server(monkeypatch)
    assert server.CLIENT_NAME == "chatgpt"
    assert server.mcp.name == "Personal Crypto Intelligence (chatgpt)"


@pytest.mark.parametrize("client", ["chatgpt", "gemini", "manus", "claude", "perplexity"])
def test_each_personal_client_can_select_its_own_key(monkeypatch, client):
    server = _load_server(monkeypatch, client_name=client)
    assert server.CLIENT_NAME == client
    assert server.API_KEY.startswith(client + "-")


def test_rejects_unknown_client(monkeypatch):
    monkeypatch.setenv("PERSONAL_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("MCP_CLIENT_NAME", "unknown")
    monkeypatch.setenv("AI_CLIENT_API_KEYS", "{}")
    monkeypatch.setenv("APP_ENV", "production")
    sys.modules.pop(MODULE, None)
    with pytest.raises(RuntimeError, match="MCP_CLIENT_NAME"):
        importlib.import_module(MODULE)


def test_rejects_weak_client_key(monkeypatch):
    monkeypatch.setenv("PERSONAL_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("MCP_CLIENT_NAME", "claude")
    monkeypatch.setenv("AI_CLIENT_API_KEYS", '{"claude":"weak"}')
    monkeypatch.setenv("APP_ENV", "production")
    sys.modules.pop(MODULE, None)
    with pytest.raises(RuntimeError, match="strong API key"):
        importlib.import_module(MODULE)


def test_rejects_insecure_production_url(monkeypatch):
    monkeypatch.setenv("PERSONAL_API_BASE_URL", "http://api.example.test")
    monkeypatch.setenv("MCP_CLIENT_NAME", "perplexity")
    monkeypatch.setenv("AI_CLIENT_API_KEYS", '{"perplexity":"' + ("p" * 40) + '"}')
    monkeypatch.setenv("APP_ENV", "production")
    sys.modules.pop(MODULE, None)
    with pytest.raises(RuntimeError, match="HTTPS"):
        importlib.import_module(MODULE)


def test_rejects_invalid_token_limits(monkeypatch):
    server = _load_server(monkeypatch)
    with pytest.raises(ValueError, match="limit"):
        server.get_spot_klines("BTCUSDT", limit=1001)
    with pytest.raises(ValueError, match="from_block"):
        server.get_cross_chain_token_intelligence("ethereum:0xabc", 10, 9)
