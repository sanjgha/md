# MD Project

A Python project with best practices for repository management, CI/CD, and security.

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
