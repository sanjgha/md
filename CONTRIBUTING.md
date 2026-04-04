# Contributing Guide

## Getting Started

1. **Install dependencies:**
   ```bash
   make install
   ```

2. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Make your changes** and test locally

4. **Run CI checks locally:**
   ```bash
   make ci
   # Or run individually:
   make lint
   make type-check
   make test
   ```

5. **Commit with conventional commits:**
   ```bash
   git commit -m "feat: add new feature"
   git commit -m "fix: resolve bug in module"
   git commit -m "docs: update README"
   git commit -m "test: add tests for feature"
   git commit -m "refactor: simplify function logic"
   ```

6. **Push and create a PR:**
   ```bash
   git push origin feature/your-feature-name
   ```

## Branch Naming

Use descriptive branch names with a prefix:

- `feature/` — new features
- `fix/` — bug fixes
- `docs/` — documentation updates
- `refactor/` — code refactoring (no logic changes)
- `test/` — test additions/updates
- `chore/` — maintenance, config updates

Example: `feature/add-user-auth`, `fix/handle-edge-case`

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat` — new feature
- `fix` — bug fix
- `docs` — documentation
- `test` — test additions/changes
- `refactor` — refactoring without feature changes
- `chore` — maintenance, dependencies, config
- `ci` — CI/CD pipeline changes

### Examples
```
feat: add user authentication
fix: handle null pointer in parser
docs: update API documentation
test: add tests for payment module
refactor: simplify data validation logic
chore: update dependencies
```

## Code Quality Standards

### Before Committing

The following checks run automatically via pre-commit hooks:

- ✅ **Black** — Code is formatted correctly
- ✅ **Ruff** — Linting rules pass
- ✅ **No secrets detected** — No API keys, credentials, etc.
- ✅ **No trailing whitespace**
- ✅ **YAML/JSON valid** — Config files are valid

If pre-commit blocks a commit, run:
```bash
make format       # Auto-fix formatting issues
make lint         # Check linting
```

### PR Checks

These run automatically on all PRs:

1. **Lint & Format Check** — Black + Ruff
2. **Type Check** — MyPy static type checking
3. **Tests** — Pytest with coverage reporting
4. **Security Scan** — Detect-secrets + Bandit + CodeQL
5. **Dependency Scan** — Safety check for vulnerabilities

All checks must pass before merging.

## Testing

### Run Tests
```bash
make test
```

### Run with Coverage
```bash
make coverage       # Generates htmlcov/index.html
```

### Write Tests

Tests go in `tests/` directory:
- File naming: `test_*.py`
- Class naming: `Test*`
- Method naming: `test_*`

Example:
```python
import pytest

class TestMyFeature:
    def test_basic_functionality(self):
        """Test the basic case."""
        assert my_function() == expected_value

    @pytest.mark.unit
    def test_edge_case(self):
        """Test edge case."""
        assert my_function(edge_value) == expected_output
```

## Making a Pull Request

1. **Push your branch:**
   ```bash
   git push origin feature/my-feature
   ```

2. **Create a PR on GitHub** with:
   - Clear title: `feat: describe what this does`
   - Description of changes
   - Reference any issues: `Closes #123`
   - Link to related PRs if any

3. **Review** — A self-review or peer review is required

4. **Wait for CI** — All checks must pass

5. **Merge** — Squash and merge (keeps history clean)

## Pull Request Template

When creating a PR, include:

```markdown
## Description
Brief description of what this PR does.

## Changes
- Change 1
- Change 2
- Change 3

## Testing
- [ ] Tests added/updated
- [ ] Ran `make test` locally
- [ ] Covered edge cases

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-reviewed the code
- [ ] Comments added for complex logic
- [ ] Documentation updated
```

## Common Commands

```bash
# Development
make install              # Install dependencies
make format               # Auto-format code
make lint                 # Run linting
make type-check           # Run type checking
make test                 # Run tests
make coverage             # Coverage report
make ci                   # Full pipeline

# Cleanup
make clean                # Remove build artifacts

# Git
git status                # Check changes
git diff                  # View changes
git log --oneline -10     # View recent commits
```

## Getting Help

- Check existing [GitHub Issues](../../issues)
- Review [SECURITY.md](SECURITY.md) for security concerns
- See [README.md](README.md) for project overview

## Code of Conduct

Be respectful, inclusive, and constructive. We follow standard open-source community guidelines.

Thanks for contributing! 🚀
