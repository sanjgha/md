.PHONY: install dev-install test test-cov lint format typecheck ci \
        frontend-install frontend-dev frontend-build frontend-test \
        generate-types clean

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

test:
	pytest tests/

test-cov:
	pytest tests/ --cov=src --cov-report=html

lint:
	black --check src/ tests/
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/

typecheck:
	mypy src/ --ignore-missing-imports

ci: lint test

frontend-install:
	cd frontend && pnpm install

frontend-dev:
	cd frontend && pnpm dev

frontend-build:
	cd frontend && pnpm build

frontend-test:
	cd frontend && pnpm test

generate-types:
	cd frontend && pnpm generate:types

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache build/ dist/ *.egg-info htmlcov/
	cd frontend && rm -rf dist node_modules
