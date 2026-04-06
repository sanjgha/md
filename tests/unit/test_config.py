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
