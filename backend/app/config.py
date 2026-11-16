from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.middleware.cors import CORSMiddleware


class Settings(BaseSettings):
    app_name: str = "Universal Binance AI Backend"
    app_env: str = "development"
    personal_api_key: str = ""
    ai_client_api_keys: str = "{}"
    log_level: str = "INFO"
    cors_allowed_origins: str = ""
    binance_spot_base_url: str = "https://api.binance.com"
    http_timeout_seconds: float = 15.0
    liquidation_collector_enabled: bool = False
    liquidation_database_path: str = "data/liquidations.sqlite3"
    order_book_collector_enabled: bool = False
    order_book_collector_jobs: str = "[]"
    order_book_database_path: str = "data/order_book_history.sqlite3"
    order_book_sample_interval_seconds: float = 1.0
    order_book_snapshot_limit: int = 1000
    order_book_stored_levels: int = 20
    aggregate_trade_collector_enabled: bool = False
    aggregate_trade_collector_jobs: str = "[]"
    aggregate_trade_database_path: str = "data/aggregate_trades.sqlite3"
    historical_kline_database_path: str = "data/historical_klines.sqlite3"
    funding_rate_database_path: str = "data/funding_rates.sqlite3"
    open_interest_database_path: str = "data/open_interest.sqlite3"
    derivatives_signal_database_path: str = "data/derivatives_signals.sqlite3"
    derivatives_ratio_database_path: str = "data/derivatives_ratios.sqlite3"
    market_confluence_database_path: str = "data/market_confluence.sqlite3"
    derivatives_collector_enabled: bool = False
    derivatives_collector_jobs: str = "[]"
    derivatives_collector_poll_seconds: int = 60
    derivatives_collector_funding_limit: int = 1000
    derivatives_collector_open_interest_limit: int = 500
    historical_collector_enabled: bool = False
    historical_collector_jobs: str = "[]"
    historical_collector_poll_seconds: int = 30
    historical_collector_initial_limit: int = 500
    news_rss_feeds: str = ""
    news_primary_source_domains: str = ""
    news_independent_source_domains: str = ""
    news_stale_after_hours: int = 168
    evm_rpc_url: str = ""
    evm_chain_name: str = ""
    evm_exchange_addresses: str = ""
    evm_max_log_block_span: int = 2000
    evm_transfer_database_path: str = "data/evm_transfers.sqlite3"
    evm_index_max_total_blocks: int = 10000
    evm_wallet_registry: str = "[]"
    evm_chain_rpc_urls: str = "[]"
    evm_chain_token_contracts: str = "[]"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()



def parse_cors_allowed_origins(value: str) -> list[str]:
    """Parse exact browser origins; reject wildcards, paths, and insecure remote HTTP."""
    origins: list[str] = []
    for raw_origin in value.split(","):
        origin = raw_origin.strip()
        if not origin:
            continue
        parsed = urlsplit(origin)
        hostname = parsed.hostname
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("CORS_ALLOWED_ORIGINS contains an invalid port") from exc
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.netloc
            or parsed.netloc.endswith(":")
            or hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or "*" in origin
            or any(character.isspace() for character in origin)
        ):
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must contain exact HTTPS origins without paths or credentials"
            )
        if parsed.scheme == "http" and hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("CORS_ALLOWED_ORIGINS permits HTTP only for localhost development origins")
        try:
            normalized_hostname = hostname.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ValueError("CORS_ALLOWED_ORIGINS contains an invalid hostname") from exc
        if not normalized_hostname or any(character in normalized_hostname for character in "/\\\\?#@"):
            raise ValueError("CORS_ALLOWED_ORIGINS contains an invalid hostname")
        default_port = 443 if parsed.scheme == "https" else 80
        host_for_origin = f"[{normalized_hostname}]" if ":" in normalized_hostname else normalized_hostname
        authority = host_for_origin if port is None or port == default_port else f"{host_for_origin}:{port}"
        canonical_origin = f"{parsed.scheme}://{authority}"
        if canonical_origin not in origins:
            origins.append(canonical_origin)
    return origins


def configure_cors_middleware(app, allowed_origins: str) -> None:
    """Enable narrow Bearer-header CORS without cookies or wildcard origins."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=parse_cors_allowed_origins(allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID"],
        allow_credentials=False,
        max_age=600,
    )
