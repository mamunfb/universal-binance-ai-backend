from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Universal Binance AI Backend"
    app_env: str = "development"
    log_level: str = "INFO"
    binance_spot_base_url: str = "https://api.binance.com"
    http_timeout_seconds: float = 15.0
    liquidation_collector_enabled: bool = False
    liquidation_database_path: str = "data/liquidations.sqlite3"
    news_rss_feeds: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
