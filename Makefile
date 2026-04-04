.PHONY: help install lint format type-check test coverage clean

help:
	@echo "Available commands:"
	@echo "  make install       - Install dev dependencies"
	@echo "  make lint          - Run linting checks"
	@echo "  make format        - Auto-format code"
	@echo "  make type-check    - Run type checking"
	@echo "  make test          - Run tests"
	@echo "  make coverage      - Run tests with coverage report"
	@echo "  make ci            - Run all CI checks (lint, type-check, test)"
	@echo "  make clean         - Remove build artifacts and cache files"

install:
	pip install -r requirements-dev.txt

lint:
	ruff check .
	black --check .

format:
	black .
	ruff check --fix .

type-check:
	mypy . --ignore-missing-imports

test:
	pytest tests/ -v

coverage:
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term
	@echo "Coverage report generated: htmlcov/index.html"

ci: lint type-check test
	@echo "✅ All CI checks passed!"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/ .mypy_cache/ htmlcov/ .coverage
	rm -rf build/ dist/ *.egg-info
