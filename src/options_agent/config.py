"""Configuration for the options agent module."""

from dataclasses import dataclass
from src.config import get_config


@dataclass
class OptionsAgentConfig:
    """Configuration dataclass for options agent settings."""

    dolt_options_url: str
    dolt_repo_path: str
    llm_model: str
    anthropic_api_key: str | None


def get_options_config() -> OptionsAgentConfig:
    """Return an OptionsAgentConfig populated from the global application config."""
    cfg = get_config()
    return OptionsAgentConfig(
        dolt_options_url=cfg.DOLT_OPTIONS_URL,
        dolt_repo_path=cfg.DOLT_REPO_PATH,
        llm_model=cfg.OPTIONS_AGENT_LLM_MODEL,
        anthropic_api_key=cfg.ANTHROPIC_API_KEY,
    )
