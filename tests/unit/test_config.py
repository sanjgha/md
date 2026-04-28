import os
import pytest
from unittest.mock import patch


def test_config_loads_from_env():
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql://test:test@localhost/testdb",
            "MARKETDATA_API_TOKEN": "test_token_123",
        },
    ):
        from importlib import reload
        import src.config as cfg_module

        reload(cfg_module)
        cfg_module.get_config.cache_clear()
        config = cfg_module.get_config()
        assert config.DATABASE_URL == "postgresql://test:test@localhost/testdb"
        assert config.MARKETDATA_API_TOKEN == "test_token_123"


def test_config_raises_on_missing_required():
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "MARKETDATA_API_TOKEN")}
    with patch.dict(os.environ, env, clear=True):
        from importlib import reload
        import src.config as cfg_module

        reload(cfg_module)
        # Patch after reload so the rebind from `from dotenv import load_dotenv` is overridden
        with patch("src.config.load_dotenv"):
            cfg_module.get_config.cache_clear()
            with pytest.raises(ValueError):
                cfg_module.get_config()


def test_config_defaults():
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql://test:test@localhost/testdb",
            "MARKETDATA_API_TOKEN": "test_token_123",
        },
    ):
        from importlib import reload
        import src.config as cfg_module

        reload(cfg_module)
        cfg_module.get_config.cache_clear()
        config = cfg_module.get_config()
        assert config.LOG_LEVEL == "INFO"
        assert config.STOCK_UNIVERSE_SIZE == 500
        assert config.MAX_RETRIES == 5


def test_config_api_fields_default():
    """APP_USERNAME/PASSWORD are optional in config (migration-only)."""
    from src.config import get_config

    env = {
        "DATABASE_URL": "postgresql://test:test@localhost/testdb",
        "MARKETDATA_API_TOKEN": "tok",
    }
    with patch.dict(os.environ, env, clear=True):
        get_config.cache_clear()
        cfg = get_config()
        assert cfg.APP_USERNAME is None
        assert cfg.APP_PASSWORD is None
        assert cfg.APP_BIND_HOST == "127.0.0.1"
        assert cfg.APP_PORT == 8000
    get_config.cache_clear()


def test_config_earnings_news_sync_defaults_to_true():
    """ENABLE_EARNINGS_SYNC and ENABLE_NEWS_SYNC default to True."""
    from src.config import get_config

    env = {
        "DATABASE_URL": "postgresql://test:test@localhost/testdb",
        "MARKETDATA_API_TOKEN": "tok",
    }
    with patch.dict(os.environ, env, clear=True):
        get_config.cache_clear()
        cfg = get_config()
        assert cfg.ENABLE_EARNINGS_SYNC is True
        assert cfg.ENABLE_NEWS_SYNC is True
    get_config.cache_clear()


def test_config_earnings_news_sync_can_be_disabled():
    """ENABLE_EARNINGS_SYNC and ENABLE_NEWS_SYNC can be set to false."""
    from src.config import get_config

    env = {
        "DATABASE_URL": "postgresql://test:test@localhost/testdb",
        "MARKETDATA_API_TOKEN": "tok",
        "ENABLE_EARNINGS_SYNC": "false",
        "ENABLE_NEWS_SYNC": "FALSE",
    }
    with patch.dict(os.environ, env, clear=True):
        get_config.cache_clear()
        cfg = get_config()
        assert cfg.ENABLE_EARNINGS_SYNC is False
        assert cfg.ENABLE_NEWS_SYNC is False
    get_config.cache_clear()


def test_config_earnings_news_sync_case_insensitive():
    """ENABLE_EARNINGS_SYNC and ENABLE_NEWS_SYNC accept case-insensitive values."""
    from src.config import get_config

    env = {
        "DATABASE_URL": "postgresql://test:test@localhost/testdb",
        "MARKETDATA_API_TOKEN": "tok",
        "ENABLE_EARNINGS_SYNC": "True",
        "ENABLE_NEWS_SYNC": "tRuE",
    }
    with patch.dict(os.environ, env, clear=True):
        get_config.cache_clear()
        cfg = get_config()
        assert cfg.ENABLE_EARNINGS_SYNC is True
        assert cfg.ENABLE_NEWS_SYNC is True
    get_config.cache_clear()
