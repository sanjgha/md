# Branch Protection Rules Setup

Branch protection rules are available on GitHub Pro for private repositories. Here's how to set them up manually:

## Manual Setup via GitHub UI

### 1. Go to Branch Protection Settings
- Navigate to your repo: https://github.com/sanjgha/md
- Click **Settings** (top right)
- Select **Branches** from the left sidebar
- Click **Add rule** under "Branch protection rules"

### 2. Configure the Rule

**Branch name pattern:** `master`

### 3. Require Pull Request Reviews
✅ **Require a pull request before merging**
- Required approving reviews: `1`
- ✅ Dismiss stale pull request approvals when new commits are pushed
- ✅ Require review from code owners (optional)
- ❌ Require approval of the most recent push

### 4. Require Status Checks to Pass
✅ **Require status checks to pass before merging**
- ✅ Require branches to be up to date before merging
- Select these status checks:
  - `Lint & Format Check`
  - `Type Check`
  - `Tests (Python 3.11)`
  - `Security Scan`
  - `All Checks Status`

### 5. Restrict Who Can Push
✅ **Restrict who can push to matching branches**
- Select yourself (only you can push directly)

### 6. Additional Rules
✅ **Require signed commits** (optional, recommended)
✅ **Require conversation resolution before merging** (optional)
❌ **Allow force pushes** (keep disabled)
❌ **Allow deletions** (keep disabled)

### 7. Save
Click **Create** or **Update** to save the rules.

## What This Enforces

Once enabled:
- ✅ No commits directly to `master`
- ✅ All PRs must have at least 1 approval (your own counts)
- ✅ All CI checks must pass
- ✅ Branch must be up-to-date before merge
- ✅ Only you can push (no accidental pushes by collaborators)

## Alternative: Make Repo Public

If you prefer to avoid GitHub Pro, you can make the repo public:
1. Go to **Settings** → **General**
2. Scroll to **Danger Zone**
3. Click **Change visibility**
4. Select **Public**
5. Confirm

Public repos support branch protection for free.

## Verify Protection is Active

After setup, you should see a green checkmark ✅ next to the branch name in the **Branches** tab.
