def test_module_version():
    from src.options_agent import __version__

    assert __version__ == "0.1.0"


def test_submodules_importable():
    import src.options_agent.data  # noqa: F401
    import src.options_agent.signals  # noqa: F401
    import src.options_agent.chain  # noqa: F401
    import src.options_agent.targets  # noqa: F401
    import src.options_agent.candidates  # noqa: F401


def test_get_options_config_returns_correct_fields(monkeypatch):
    """get_options_config() populates all fields from environment."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("MARKETDATA_API_TOKEN", "test-token")
    monkeypatch.setenv("DOLT_OPTIONS_URL", "mysql://localhost:3306/options")
    monkeypatch.setenv("DOLT_REPO_PATH", "/tmp/dolt")
    monkeypatch.setenv("OPTIONS_AGENT_LLM_MODEL", "claude-3-haiku-20240307")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    # Need to clear lru_cache since get_config is cached
    from src.config import get_config

    get_config.cache_clear()

    from src.options_agent.config import get_options_config

    cfg = get_options_config()

    assert cfg.dolt_options_url == "mysql://localhost:3306/options"
    assert cfg.dolt_repo_path == "/tmp/dolt"
    assert cfg.llm_model == "claude-3-haiku-20240307"
    assert cfg.anthropic_api_key == "sk-test-key"

    get_config.cache_clear()  # cleanup
