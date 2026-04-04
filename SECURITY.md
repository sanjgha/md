# Security Policy

## Reporting Security Vulnerabilities

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security vulnerabilities by emailing `security@example.com` with:

- Description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact
- Suggested fix (if you have one)

We take security seriously and will acknowledge your report within 48 hours and provide a status update within one week.

## Security Measures

This project includes the following security controls:

### Pre-commit Hooks
- **detect-secrets** prevents committing credentials and API keys
- All commits are scanned before being allowed to push

### Automated Scanning
- **CodeQL** — Static Application Security Testing (SAST) via GitHub
- **Bandit** — Python security linter
- **Safety** — Dependency vulnerability scanner
- **Dependabot** — Automated dependency updates with security patches

### Code Quality
- **Black** — Code formatting for consistency
- **Ruff** — Linting to catch common bugs
- **MyPy** — Type checking to prevent type-related errors
- **Pytest** — Automated testing

### Branch Protection
- `master` branch requires PR reviews before merge
- All CI checks must pass before merging
- Branch must be up to date with main

## Dependency Management

- Dependencies are automatically scanned for known vulnerabilities via Dependabot
- Security patches are auto-deployed as PRs every Monday
- We keep dependencies up to date with minor/patch version updates
- All dependencies are tracked in `requirements-dev.txt`

## Responsible Disclosure

If you discover a security issue, please:
1. **Do not** publicly disclose it until we've had time to fix it
2. **Do** give us reasonable time to patch (typically 30 days)
3. **Do** provide technical details to help us understand and fix the issue

Thank you for helping keep this project secure! 🔒
