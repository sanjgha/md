# Setting Up Branch Protection Rules in GitHub UI

This guide provides step-by-step instructions to enable branch protection rules for your repository.

## ⚠️ Prerequisites

**Your repository must be:**
- ✅ Public (branch protection is free for public repos)
- OR
- ✅ Private with GitHub Pro subscription

If your repo is private and you don't have GitHub Pro:
- Option 1: Upgrade to GitHub Pro ($4/month)
- Option 2: Make your repo public (Settings → Danger Zone → Change visibility)

---

## Step-by-Step Setup

### Step 1: Go to Settings

1. Navigate to your repo: **https://github.com/sanjgha/md**
2. Click the **Settings** tab (near the top right)
3. You should see a gear icon ⚙️

![Settings Location](images/step1-settings.png)

---

### Step 2: Navigate to Branches

1. In the left sidebar, find **Code and automation** section
2. Click **Branches**
3. You'll see "Branch protection rules" section

![Branches Menu](images/step2-branches.png)

---

### Step 3: Add Branch Protection Rule

1. Click **Add rule** button
2. Under "Branch name pattern", type: **`master`**

This protects your `master` branch.

![Add Rule](images/step3-add-rule.png)

---

### Step 4: Configure Protection Options

#### Option 4a: Require a Pull Request Before Merging

✅ **Check this box:** "Require a pull request before merging"

Once checked, new options appear:

- **Required number of approvals before merging:** Set to **`1`**
  - This means you must approve your own PRs (enforces discipline)

- ✅ **Check:** "Dismiss stale pull request approvals when new commits are pushed"
  - Old approvals become invalid after new commits

- ❌ **Don't check:** "Require approval of the most recent push"
  - Not necessary for solo development

- ❌ **Don't check:** "Require review from code owners"
  - Not needed unless you have a CODEOWNERS file

![PR Requirements](images/step4a-pr-requirements.png)

---

#### Option 4b: Require Status Checks to Pass

✅ **Check this box:** "Require status checks to pass before merging"

Once checked:

✅ **Check:** "Require branches to be up to date before merging"
- Branch must be rebased with `master` before merge
- Prevents conflicts

**Status checks to require:**

Look for a dropdown that says "Search for status checks that have recently been provided"

Search for and select these checks (in this order):
1. ✅ `Lint & Format Check`
2. ✅ `Type Check`
3. ✅ `Tests (Python 3.11)`
4. ✅ `Security Scan`
5. ✅ `All Checks Status`

If you don't see all of them immediately, make sure CI has run at least once (it has).

![Status Checks](images/step4b-status-checks.png)

---

#### Option 4c: Restrict Who Can Push

⏭️ **Skip this for now**

"Restrict who can push to matching branches" is optional. For solo development, the PR requirement is sufficient.

---

#### Option 4d: Require Signed Commits (Optional)

✅ **Recommended:** Check "Require signed commits"

This ensures all commits are cryptographically signed, improving audit trails.

⚠️ **Only do this if you've set up GPG signing.**

If you haven't, **leave this unchecked.**

![Signed Commits](images/step4d-signed-commits.png)

---

#### Option 4e: Require Conversation Resolution

❌ **Leave unchecked:** "Require conversation resolution before merging"

This is for team projects where you need all comments resolved.

---

#### Option 4f: Additional Rules

- ❌ **Don't check:** "Allow force pushes"
  - Prevents rewriting history

- ❌ **Don't check:** "Allow deletions"
  - Prevents accidentally deleting the branch

![Other Options](images/step4f-other-options.png)

---

### Step 5: Save the Rule

1. Scroll to the bottom of the form
2. Click the **Create** button (or **Update** if editing)
3. You should see a success message

![Save Rule](images/step5-save.png)

---

## Verify Protection is Enabled

After saving:

1. Go back to your repo's main page
2. Look at the **Branches** tab (near Code, Issues, PRs)
3. You should see a **shield icon** ✅ next to `master`
4. Click on it to see the protection rules you just configured

![Verification](images/step6-verify.png)

---

## What's Now Protected

With these settings, `master` is now protected:

✅ **No direct pushes allowed**
- You cannot do `git push origin master` anymore
- All changes require a PR

✅ **All PRs require approval**
- You must review your own PR
- Enforces you check your changes before merge

✅ **All CI checks must pass**
- Tests, linting, type-checking, security scans
- PRs can't be merged if any check fails

✅ **Branches must be up to date**
- If `master` has new commits, PR branch must be rebased
- Prevents merge conflicts

---

## Workflow with Branch Protection

Here's how you'll now work:

```bash
# 1. Create a feature branch
git checkout -b feature/my-feature

# 2. Make changes and commit
git add .
git commit -m "feat: add new feature"

# 3. Push to GitHub
git push origin feature/my-feature

# 4. Create a PR on GitHub (web UI)
# → CI runs automatically
# → All checks must pass ✅

# 5. Review your own PR on GitHub
# → You must approve it

# 6. Merge the PR (web UI)
# → Now you can merge to master

# 7. Pull changes to local master
git checkout master
git pull origin master
```

---

## Troubleshooting

### "Require status checks to pass" option is grayed out

This means CI hasn't run yet on your repo. Solution:
1. Wait 5-10 minutes for CI to run
2. Push another commit to `master`
3. Come back and refresh this page

### Status checks aren't showing up in the dropdown

If you don't see your checks:
1. Make sure CI has run: https://github.com/sanjgha/md/actions
2. Refresh the settings page
3. The checks should appear after the first CI run

### Can't create a rule (403 error)

Your repo is private and you don't have GitHub Pro. Either:
- Upgrade to GitHub Pro: https://github.com/account/upgrade
- Make repo public: Settings → Danger Zone → Change visibility

### Need to undo/remove the rule?

1. Go back to Settings → Branches
2. Find the rule for `master`
3. Click the **Delete** button
4. Confirm

---

## Next: Test the Protection

Once enabled, try this:

```bash
# Try to push directly to master (this should FAIL)
git checkout master
echo "test" >> README.md
git commit -am "test: direct push"
git push origin master
# → Should fail with: "protected branch"
```

This confirms protection is working! ✅

To actually make changes, use the PR workflow:

```bash
# Create a branch instead
git checkout -b feature/test
echo "test" >> README.md
git commit -am "test: via PR"
git push origin feature/test

# Then create a PR on GitHub UI
# Review and merge through the web interface
```

---

## Summary

| Step | What to Do | Value |
|------|-----------|-------|
| 1-3 | Go to Settings → Branches → Add rule for `master` | Basic protection |
| 4a | Require 1 PR approval | Enforces code review |
| 4b | Require status checks (select all 5) | Ensures quality |
| 4b | Check "up to date before merge" | Prevents conflicts |
| 5 | Save | Activates protection |

**Total time:** ~3 minutes ⏱️

**Result:** Your `master` branch is now protected from accidental commits! 🔒
