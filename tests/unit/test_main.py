"""Tests for the CLI entry point."""

import pytest
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
