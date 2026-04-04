# Code Coverage Tracking with Codecov

This project uses Codecov to track test coverage over time and enforce coverage thresholds.

## What is Codecov?

Codecov is a code coverage analysis tool that:
- Tracks test coverage percentage over time
- Reports coverage in pull requests
- Enforces minimum coverage thresholds
- Provides historical coverage trends
- Integrates with GitHub for PR comments

## Automatic Setup

Codecov automatically activates when:
1. Your repo is public OR connected via GitHub OAuth
2. Coverage reports are uploaded from CI (already configured in `.github/workflows/ci.yml`)
3. The codecov-action runs after tests complete

**The CI workflow already uploads coverage—no manual setup needed!**

## View Your Coverage

### 1. GitHub Integration
Codecov will post coverage reports on your PRs automatically once activated:

```
Coverage Report
📊 70.5% coverage with 42 lines covered and 18 lines uncovered
```

### 2. Codecov Dashboard
Visit: https://codecov.io

1. Sign in with GitHub
2. Click **+New organization**
3. Select your GitHub account
4. Authorize Codecov
5. Your repo will appear in the list
6. Click on your repo to view detailed coverage reports

### 3. Local Coverage Report
Run locally anytime:

```bash
make coverage       # Generates htmlcov/index.html
```

Open `htmlcov/index.html` in your browser to see:
- Overall coverage percentage
- Coverage by file
- Missing lines highlighted in red
- Coverage trends

## Coverage Thresholds

Configured in `.codecov.yml`:

- **Patch coverage:** Must be ≥80% (new code in the PR)
- **Project coverage:** Must be ≥70% (entire codebase)

If coverage drops below thresholds, Codecov will comment on your PR with details.

## Coverage Badge

Add a coverage badge to your README:

```markdown
[![Codecov Coverage](https://codecov.io/gh/sanjgha/md/branch/master/graph/badge.svg)](https://codecov.io/gh/sanjgha/md)
```

This shows current coverage percentage with a clickable link to Codecov.

## Improving Coverage

### 1. Check Coverage Locally
```bash
make coverage
```

### 2. Identify Uncovered Code
- Open `htmlcov/index.html`
- Look for red lines (uncovered)
- Add tests for those lines

### 3. Run Tests with Coverage
```bash
make test       # Run tests
make coverage   # Generate detailed report
```

### 4. Write Tests
Example test file: `tests/test_example.py`

```python
def my_function(x):
    if x > 0:
        return x * 2
    return 0

# Test both paths
def test_positive():
    assert my_function(5) == 10

def test_zero():
    assert my_function(0) == 0
```

## CI Integration

The CI workflow automatically:
1. Runs `pytest` with coverage
2. Generates `coverage.xml`
3. Uploads to Codecov via `codecov-action`

Check `.github/workflows/ci.yml` for details.

## Coverage Report Files

Generated during `make test`:
- `.coverage` — Binary coverage data
- `coverage.xml` — XML report for Codecov
- `.pytest_cache/` — Pytest cache

(These are in `.gitignore` and won't be committed)

## Resources

- Codecov Docs: https://docs.codecov.io
- Coverage.py (Python coverage tool): https://coverage.readthedocs.io
- Pytest Coverage Plugin: https://pytest-cov.readthedocs.io
