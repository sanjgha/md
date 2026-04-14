"""Unit tests for schedule job callbacks."""

from unittest.mock import MagicMock, patch


def test_run_eod_job_returns_result_count():
    """run_eod_job returns the number of matched scanner results."""
    mock_db = MagicMock()

    # Mock Stock query to return empty list (no candles = no results)
    mock_db.query.return_value.options.return_value.all.return_value = []

    from src.api.schedule.jobs import run_eod_job

    count = run_eod_job(mock_db)
    assert count == 0


def test_run_pre_close_job_returns_result_count():
    """run_pre_close_job returns the number of matched pre-close results."""
    mock_db = MagicMock()

    with patch("src.scanner.pre_close_executor.PreCloseExecutor") as MockExecutor:
        MockExecutor.return_value.run.return_value = [MagicMock(), MagicMock()]
        from src.api.schedule.jobs import run_pre_close_job

        count = run_pre_close_job(mock_db)

    assert count == 2