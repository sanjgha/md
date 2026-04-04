# MD Project

A Python project with best practices for repository management, CI/CD, and security.

[![Tests](https://github.com/sanjgha/md/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/sanjgha/md/actions/workflows/ci.yml)
[![Codecov Coverage](https://img.shields.io/codecov/c/github/sanjgha/md/master?logo=codecov)](https://codecov.io/gh/sanjgha/md)

## Quick Start

### Setup
```bash
make install       # Install development dependencies
```

### Development
```bash
make test          # Run tests
make lint          # Run linting checks
make format        # Auto-format code
make type-check    # Run type checking
make ci             # Run full CI pipeline locally
```

### Testing
```bash
make coverage      # Generate coverage report (opens htmlcov/index.html)
```

## Project Features

### ✅ CI/CD Pipeline
- **GitHub Actions** workflows run on every push and PR
- Tests, linting, type checking, and security scans
- Coverage reports uploaded to Codecov
- Full pipeline configured in `.github/workflows/ci.yml`

### 🔒 Security
- **Pre-commit hooks** prevent committing secrets
- **CodeQL** static analysis via GitHub
- **Bandit** Python security linter
- **Safety** dependency vulnerability scanner
- **Dependabot** automated security updates
- See [SECURITY.md](SECURITY.md) for details

### 📦 Dependency Management
- **Dependabot** auto-creates PRs for updates every Monday
- Automatically groups dev vs runtime dependencies
- Security patches get priority

### 📋 Code Quality
- **Black** — code formatting (100 char line length)
- **Ruff** — fast Python linting with auto-fixes
- **MyPy** — type checking
- **Pytest** — test framework with markers
- **Coverage** — test coverage reporting

## Setup & Configuration

### Branch Protection
Branch protection rules prevent accidental commits to `master`.
See [Branch Protection Setup](docs/BRANCH_PROTECTION_SETUP.md) for configuration.

### Code Coverage
Coverage tracking with Codecov shows test coverage trends and enforces minimum thresholds.
See [Codecov Setup](docs/CODECOV_SETUP.md) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Making changes
- Running tests locally
- Creating pull requests
- Commit message conventions

## Security

Please see [SECURITY.md](SECURITY.md) for information on reporting security vulnerabilities.

## License

[Add your license here]
