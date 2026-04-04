# Branch Protection Rules Setup

Branch protection rules are available on GitHub Pro for private repositories, or for free on public repositories.

## Prerequisites

Your repository must be:
- ✅ **Public** (free branch protection)
- OR
- ✅ **Private with GitHub Pro** ($4/month)

If your repo is private and you don't have GitHub Pro:
- **Option A:** Upgrade to GitHub Pro
- **Option B:** Make your repo public (free, but visible to everyone)

## Setup Options

### Option 1: Detailed Step-by-Step (Recommended for First Time)

For a complete walkthrough with screenshots and detailed explanations:

👉 **See: [BRANCH_PROTECTION_GITHUB_UI.md](BRANCH_PROTECTION_GITHUB_UI.md)**

This guide includes:
- Screenshots for each step
- Explanations of each option
- Common troubleshooting
- How to test that protection works

**Time needed:** ~3 minutes

### Option 2: Quick Reference

**What to configure:**
1. Go to Settings → Branches → Add rule
2. Branch name pattern: `master`
3. ✅ Require pull request before merging (1 approval)
4. ✅ Require status checks to pass
   - Select: `Lint & Format Check`, `Type Check`, `Tests (Python 3.11)`, `Security Scan`, `All Checks Status`
5. ✅ Require branches to be up to date before merging
6. Click **Create**

## What This Enforces

Once enabled:
- ✅ No direct commits to `master`
- ✅ All changes require a pull request
- ✅ All CI checks must pass before merging
- ✅ Branches must be up-to-date before merge
- ✅ At least 1 approval required (your own counts)

## Verify Protection is Active

After setup:
1. Go to your repo's **Branches** tab
2. Look for a **shield icon** ✅ next to `master`
3. Click it to view the protection rules

## Next Steps

After enabling branch protection, test it:

```bash
# This should FAIL (protected branch)
git push origin master

# Instead, use PR workflow
git checkout -b feature/my-feature
git push origin feature/my-feature
# Create PR on GitHub, review, and merge through web UI
```

## Troubleshooting

**Can't create rule (403 error)?**
- Your repo is private without GitHub Pro
- Upgrade to GitHub Pro OR make repo public

**Status checks not showing in dropdown?**
- Wait for CI to run at least once
- Refresh the settings page
- They should appear after CI completes

**Need detailed instructions?**
- See [BRANCH_PROTECTION_GITHUB_UI.md](BRANCH_PROTECTION_GITHUB_UI.md)
