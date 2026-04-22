"""Configuration module with lazy-loaded settings via get_config() factory."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


class Config:
    """Application configuration loaded from environment variables."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        self.MARKETDATA_API_TOKEN = os.getenv("MARKETDATA_API_TOKEN")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE = os.getenv("LOG_FILE", "logs/market_data.log")
        self.GLM_API_KEY = os.getenv("GLM_API_KEY")  # Optional: for GLM-5.1 trading analysis

        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is required")
        if not self.MARKETDATA_API_TOKEN:
            raise ValueError("MARKETDATA_API_TOKEN environment variable is required")

        self.STOCK_UNIVERSE_SIZE = 500
        self.MAX_RETRIES = 5
        self.RETRY_BACKOFF_BASE = 1
        self.CONNECTION_POOL_MIN = 5
        self.CONNECTION_POOL_MAX = 20
        self.DAILY_CANDLE_RETENTION_YEARS = 1
        self.INTRADAY_RETENTION_DAYS = 7
        self.QUOTE_RETENTION_DAYS = 7
        self.API_RATE_LIMIT_DELAY = 0.1

        # API server settings (APP_USERNAME/APP_PASSWORD read only by migration)
        self.APP_USERNAME = os.getenv("APP_USERNAME")
        self.APP_PASSWORD = os.getenv("APP_PASSWORD")
        self.APP_BIND_HOST = os.getenv("APP_BIND_HOST", "127.0.0.1")
        self.APP_PORT = int(os.getenv("APP_PORT", "8000"))


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the singleton Config instance, loading .env if present."""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    return Config()
