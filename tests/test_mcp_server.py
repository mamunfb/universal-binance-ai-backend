"""Contract tests for the private MCP adapter."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

MODULE = "mcp_server.server"
SERVER_PATH = Path(__file__).resolve().parents[1] / "mcp-server" / "server.py"


def _execute_server_module():
    sys.modules.pop(MODULE, None)
    spec = importlib.util.spec_from_file_location(MODULE, SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load MCP adapter from {SERVER_PATH}")
    server = importlib.util.module_from_spec(spec)
    sys.modules[MODULE] = server
    spec.loader.exec_module(server)
    return server


def _load_server(monkeypatch, client_name="chatgpt", base_url="https://api.example.test"):
    keys = {
        name: f"{name}-" + ("x" * 40)
        for name in ("chatgpt", "gemini", "manus", "claude", "perplexity")
    }
    monkeypatch.setenv("PERSONAL_API_BASE_URL", base_url)
    monkeypatch.setenv("MCP_CLIENT_NAME", client_name)
    monkeypatch.setenv("AI_CLIENT_API_KEYS", json.dumps(keys))
    monkeypatch.setenv("APP_ENV", "production")
    return _execute_server_module()


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
        _execute_server_module()


def test_rejects_weak_client_key(monkeypatch):
    monkeypatch.setenv("PERSONAL_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("MCP_CLIENT_NAME", "claude")
    monkeypatch.setenv("AI_CLIENT_API_KEYS", '{"claude":"weak"}')
    monkeypatch.setenv("APP_ENV", "production")
    sys.modules.pop(MODULE, None)
    with pytest.raises(RuntimeError, match="strong API key"):
        _execute_server_module()


def test_rejects_insecure_production_url(monkeypatch):
    monkeypatch.setenv("PERSONAL_API_BASE_URL", "http://api.example.test")
    monkeypatch.setenv("MCP_CLIENT_NAME", "perplexity")
    monkeypatch.setenv("AI_CLIENT_API_KEYS", '{"perplexity":"' + ("p" * 40) + '"}')
    monkeypatch.setenv("APP_ENV", "production")
    sys.modules.pop(MODULE, None)
    with pytest.raises(RuntimeError, match="HTTPS"):
        _execute_server_module()


def test_stored_funding_history_tool_uses_read_only_api_route(monkeypatch):
    server = _load_server(monkeypatch)
    captured = {}

    def fake_get(path, params=None):
        captured["path"] = path
        captured["params"] = params
        return {"status": "COMPLETED", "events": []}

    monkeypatch.setattr(server, "_get", fake_get)
    result = server.get_stored_funding_rate_history(
        "btcusdt", start_time_ms=100, end_time_ms=200, limit=25
    )
    assert result["status"] == "COMPLETED"
    assert captured["path"] == "/api/v1/history/funding-rates/USD_M/BTCUSDT"
    assert captured["params"] == {"start_time_ms": 100, "end_time_ms": 200, "limit": 25}


def test_rejects_invalid_token_limits(monkeypatch):
    server = _load_server(monkeypatch)
    with pytest.raises(ValueError, match="limit"):
        server.get_spot_klines("BTCUSDT", limit=1001)
    with pytest.raises(ValueError, match="from_block"):
        server.get_cross_chain_token_intelligence("ethereum:0xabc", 10, 9)


class _FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.is_success = 200 <= status_code < 300

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeClient:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, *_args, **_kwargs):
        return self.response


def test_get_preserves_success_data_quality_metadata(monkeypatch):
    server = _load_server(monkeypatch)
    payload = {
        "status": "INCOMPLETE",
        "source": "test-provider",
        "generated_at": "2026-11-10T00:00:00Z",
        "coverage": {"complete": False},
        "missing_data": ["sample"],
        "warning": "Partial coverage",
    }
    monkeypatch.setattr(
        server.httpx, "Client",
        lambda **_kwargs: _FakeClient(_FakeResponse(200, payload)),
    )
    assert server._get("/read-only") == payload


def test_get_returns_structured_validation_error_and_request_id(monkeypatch):
    server = _load_server(monkeypatch)
    payload = {
        "status": "FAILED",
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid request",
            "details": [{"location": ["query", "limit"]}],
        },
        "request_id": "request-123",
    }
    monkeypatch.setattr(
        server.httpx, "Client",
        lambda **_kwargs: _FakeClient(
            _FakeResponse(422, payload, {"X-Request-ID": "request-123"})
        ),
    )
    result = server._get("/read-only")
    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert result["error"]["details"] == payload["error"]["details"]
    assert result["request_id"] == "request-123"
    assert result["retryable"] is False


def test_get_marks_rate_limit_as_retryable(monkeypatch):
    server = _load_server(monkeypatch)
    monkeypatch.setattr(
        server.httpx, "Client",
        lambda **_kwargs: _FakeClient(_FakeResponse(429, {})),
    )
    result = server._get("/read-only")
    assert result["error"]["code"] == "RATE_LIMITED"
    assert result["http_status"] == 429
    assert result["retryable"] is True


def test_get_rejects_invalid_success_json(monkeypatch):
    server = _load_server(monkeypatch)
    monkeypatch.setattr(
        server.httpx, "Client",
        lambda **_kwargs: _FakeClient(_FakeResponse(200, ValueError("bad json"))),
    )
    result = server._get("/read-only")
    assert result["error"]["code"] == "UPSTREAM_INVALID_RESPONSE"


def test_get_marks_authentication_error_non_retryable(monkeypatch):
    server = _load_server(monkeypatch)
    monkeypatch.setattr(
        server.httpx, "Client",
        lambda **_kwargs: _FakeClient(_FakeResponse(401, {})),
    )
    result = server._get("/read-only")
    assert result["error"]["code"] == "UNAUTHORIZED"
    assert result["retryable"] is False


def test_get_normalizes_fastapi_nested_error_detail(monkeypatch):
    server = _load_server(monkeypatch)
    payload = {
        "detail": {
            "status": "FAILED",
            "error": {"code": "UPSTREAM_TIMEOUT", "message": "Provider timed out"},
            "request_id": "nested-456",
        }
    }
    monkeypatch.setattr(
        server.httpx, "Client",
        lambda **_kwargs: _FakeClient(
            _FakeResponse(504, payload, {"X-Request-ID": "nested-456"})
        ),
    )
    result = server._get("/read-only")
    assert result["error"]["code"] == "UPSTREAM_TIMEOUT"
    assert result["request_id"] == "nested-456"
    assert result["retryable"] is True


def test_get_handles_connection_failure_without_leaking_exception(monkeypatch):
    server = _load_server(monkeypatch)

    class _FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, *_args, **_kwargs):
            raise server.httpx.ConnectError("private host and details")

    monkeypatch.setattr(server.httpx, "Client", lambda **_kwargs: _FailingClient())
    result = server._get("/read-only")
    assert result["error"]["code"] == "UPSTREAM_CONNECTION_ERROR"
    assert result["retryable"] is True
    assert "private host" not in str(result)


def test_spot_futures_basis_mcp_tool_calls_fixed_read_only_route(monkeypatch):
    server = _load_server(monkeypatch)
    calls = []
    monkeypatch.setattr(server, "_get", lambda path, params=None: calls.append((path, params)) or {"status": "COMPLETED"})
    result = server.get_spot_futures_basis("btcusdt")
    assert result["status"] == "COMPLETED"
    assert calls == [("/api/v1/analysis/spot-futures/basis/BTCUSDT", None)]


def test_historical_collector_status_mcp_tool_calls_fixed_route(monkeypatch):
    server = _load_server(monkeypatch)
    calls = []
    monkeypatch.setattr(
        server, "_get",
        lambda path, params=None: calls.append((path, params)) or {"status": "DISABLED"},
    )
    result = server.get_historical_collector_status()
    assert result["status"] == "DISABLED"
    assert calls == [("/api/v1/history/collector/status", None)]


def test_market_evidence_mcp_tool_calls_fixed_read_only_route(monkeypatch):
    server = _load_server(monkeypatch)
    calls = []
    monkeypatch.setattr(server, "_get", lambda path, params=None: calls.append((path, params)) or {"status": "COMPLETED"})
    result = server.get_market_evidence_snapshot("btcusdt")
    assert result["status"] == "COMPLETED"
    assert calls == [("/api/v1/analysis/market-evidence/BTCUSDT", None)]
