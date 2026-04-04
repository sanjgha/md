"""Example test file."""

import pytest


class TestExample:
    """Example test class."""

    def test_basic_assertion(self) -> None:
        """Test basic assertion."""
        assert True

    def test_equality(self) -> None:
        """Test equality assertion."""
        assert 1 + 1 == 2

    @pytest.mark.unit
    def test_string_contains(self) -> None:
        """Test string contains assertion."""
        text = "hello world"
        assert "world" in text
