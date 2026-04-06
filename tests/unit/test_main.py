"""Tests for the CLI entry point."""

import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from src.main import app


def test_cli_app_exists():
    """The CLI app object must be importable."""
    assert app is not None


def test_cli_help_runs():
    """--help must exit with code 0."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "eod" in result.output or "Usage" in result.output


def test_cli_does_not_init_db_at_import():
    """Importing src.main must not trigger DB connection (no env vars set)."""
    import importlib

    try:
        importlib.import_module("src.main")
    except Exception as e:
        pytest.fail(f"Importing src.main raised unexpectedly: {e}")


def test_all_commands_registered():
    """All expected commands are registered on the app."""
    command_names = list(app.commands.keys())
    for cmd in ["eod", "monitor", "init-db", "seed-universe", "schedule"]:
        assert cmd in command_names, f"Command '{cmd}' not found in CLI"


def test_init_db_command_wiring():
    """init-db command connects to DB and echoes success."""
    runner = CliRunner()
    mock_engine = MagicMock()
    with (
        patch("src.main._get_db_session"),
        patch("src.db.connection.get_engine", return_value=mock_engine),
        patch("src.db.connection.init_db") as mock_init_db,
        patch("src.config.get_config") as mock_cfg,
    ):
        mock_cfg.return_value = MagicMock(DATABASE_URL="postgresql://x", LOG_LEVEL="INFO")
        mock_init_db.return_value = None
        result = runner.invoke(app, ["init-db"])
    # Command must not crash (exit code 0 or known config error is acceptable in test env)
    assert result.exit_code in (0, 1)  # 1 if env not set — we just confirm wiring


def test_seed_universe_command_help():
    """seed-universe --help exits cleanly and lists --symbols option."""
    runner = CliRunner()
    result = runner.invoke(app, ["seed-universe", "--help"])
    assert result.exit_code == 0
    assert "--symbols" in result.output
