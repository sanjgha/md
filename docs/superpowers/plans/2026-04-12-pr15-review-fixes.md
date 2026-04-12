# PR 15 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all Critical and Important logic/quality issues found in the PR 15 watchlist code review (LIN-68 through LIN-75).

**Architecture:** All fixes are in `src/api/watchlists/` (service, schemas, routes). Tests live in `tests/unit/api/` and `tests/integration/api/`. The EOD consolidation removes dead code from `WatchlistService` and adds a second-run integration test against `WatchlistGenerationService`. Each task is independent and commits separately.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, pytest + testcontainers (PostgreSQL 16)

**Working directory:** `.worktrees/fix/pr15-review-fixes` (branch `fix/pr15-review-fixes`)

---

## File Map

| File | Changes |
|------|---------|
| `src/api/watchlists/service.py` | Task 1 (remove EOD methods from WatchlistService), Task 4 (fix `== 4`), Task 5 (update_watchlist allow None category_id) |
| `src/api/watchlists/schemas.py` | Task 3 (add is_system/sort_order to CategoryResponse), Task 5 (WatchlistUpdate sentinel pattern) |
| `src/api/watchlists/routes.py` | Task 2 (clone category ownership), Task 5 (exclude_unset) |
| `tests/unit/api/test_watchlist_service.py` | Tasks 1, 4 |
| `tests/integration/api/test_watchlists.py` | Task 2 (uncategorized), Task 5 |
| `tests/integration/api/test_watchlists_categories_and_clone.py` | Tasks 2 (clone), 3 |
| `tests/integration/test_watchlist_eod.py` | Task 1 (second-run test) |
| `.gitignore` | Task 6 |

---

## Task 1: Consolidate dual EOD service classes (LIN-68 + LIN-69)

**Files:**
- Modify: `src/api/watchlists/service.py`
- Modify: `tests/unit/api/test_watchlist_service.py`
- Modify: `tests/integration/test_watchlist_eod.py`

**Context:** `WatchlistService` has 5 EOD-specific methods (`generate_from_scanner_results`, `_create_or_replace_watchlist`, `_create_or_append_watchlist`, `_get_or_create_scanner_category`, `_format_scanner_name`) that duplicate `WatchlistGenerationService` with incompatible `watchlist_mode="static"` vs `"replace"/"append"`. Production (`main.py:145`) uses `WatchlistGenerationService`. The second-run replace/append semantics are untested. Remove the duplicate from `WatchlistService`; add a second-run integration test to `WatchlistGenerationService`.

- [ ] **Step 1: Write the failing integration test for second-run replace semantics**

Add to `tests/integration/test_watchlist_eod.py`:

```python
def test_generate_twice_replaces_today_and_appends_history(db_session: Session):
    """Second EOD run replaces Today symbols and accumulates History symbols (no duplicates)."""
    from datetime import date, datetime
    from typing import cast
    from src.api.watchlists.service import WatchlistGenerationService
    from src.db.models import ScannerResult, Stock, User, Watchlist, WatchlistSymbol

    user = User(username="eod_user2", password_hash="hash")
    db_session.add(user)
    stock_a = Stock(symbol="RUN1", name="Run One")
    stock_b = Stock(symbol="RUN2", name="Run Two")
    db_session.add_all([stock_a, stock_b])
    db_session.commit()

    # First run: only stock_a matches
    result1 = ScannerResult(
        stock_id=stock_a.id,
        scanner_name="momentum",
        result_metadata={"reason": "day1"},
        matched_at=datetime.now(),
    )
    db_session.add(result1)
    db_session.commit()

    svc = WatchlistGenerationService(db_session)
    svc.generate_from_scanner_results("momentum", date.today(), cast(int, user.id))

    # Verify Today has 1 symbol, History has 1 symbol
    today_wl = db_session.query(Watchlist).filter_by(
        user_id=user.id, scanner_name="momentum", watchlist_mode="replace"
    ).first()
    history_wl = db_session.query(Watchlist).filter_by(
        user_id=user.id, scanner_name="momentum", watchlist_mode="append"
    ).first()
    assert today_wl is not None
    assert history_wl is not None
    assert db_session.query(WatchlistSymbol).filter_by(watchlist_id=today_wl.id).count() == 1
    assert db_session.query(WatchlistSymbol).filter_by(watchlist_id=history_wl.id).count() == 1

    # Second run: only stock_b matches (different stock)
    result2 = ScannerResult(
        stock_id=stock_b.id,
        scanner_name="momentum",
        result_metadata={"reason": "day2"},
        matched_at=datetime.now(),
    )
    db_session.add(result2)
    db_session.commit()

    svc.generate_from_scanner_results("momentum", date.today(), cast(int, user.id))

    db_session.expire_all()
    # Today must have exactly 1 symbol (stock_b only — replaced, not accumulated)
    assert db_session.query(WatchlistSymbol).filter_by(watchlist_id=today_wl.id).count() == 1
    today_sym = db_session.query(WatchlistSymbol).filter_by(watchlist_id=today_wl.id).first()
    assert today_sym.stock_id == stock_b.id

    # History must have 2 symbols (stock_a from run1, stock_b from run2)
    assert db_session.query(WatchlistSymbol).filter_by(watchlist_id=history_wl.id).count() == 2

    # No duplicate watchlists created
    assert db_session.query(Watchlist).filter_by(
        user_id=user.id, scanner_name="momentum", watchlist_mode="replace"
    ).count() == 1
    assert db_session.query(Watchlist).filter_by(
        user_id=user.id, scanner_name="momentum", watchlist_mode="append"
    ).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/ubuntu/projects/md/.worktrees/fix/pr15-review-fixes
python3 -m pytest tests/integration/test_watchlist_eod.py::test_generate_twice_replaces_today_and_appends_history -v --no-header 2>&1 | tail -20
```

Expected: FAIL (test doesn't exist yet or WatchlistGenerationService has a bug revealed by second run)

- [ ] **Step 3: Remove EOD methods from WatchlistService**

In `src/api/watchlists/service.py`, delete lines 551–804 (the `generate_from_scanner_results`, `_get_or_create_scanner_category`, `_create_or_replace_watchlist`, `_create_or_append_watchlist`, and `_format_scanner_name` methods from `WatchlistService`). The class ends after `_format_scanner_name` at line 804. Keep everything from line 17 to 550 (CRUD methods), then keep `WatchlistGenerationService` (line 807 onward) unchanged.

After deletion, `WatchlistService` ends with:

```python
    def _format_scanner_name(self, scanner_name: str) -> str:
        # DELETE THIS AND EVERYTHING BELOW UP TO WatchlistGenerationService
```

The last method in `WatchlistService` after deletion should be `get_watchlists_grouped` (currently ends at line 549).

- [ ] **Step 4: Remove unit tests that tested the deleted WatchlistService EOD methods**

In `tests/unit/api/test_watchlist_service.py`, find and delete any test functions that reference `generate_from_scanner_results`, `_create_or_replace_watchlist`, `_create_or_append_watchlist` when called on a `WatchlistService` instance (not `WatchlistGenerationService`). These are tests of code that no longer exists.

```bash
grep -n "generate_from_scanner_results\|_create_or_replace\|_create_or_append" tests/unit/api/test_watchlist_service.py
```

Delete those test functions entirely.

- [ ] **Step 5: Run all tests to verify new integration test passes and no regressions**

```bash
python3 -m pytest tests/unit/api/test_watchlist_service.py tests/integration/test_watchlist_eod.py -v --no-header 2>&1 | tail -20
```

Expected: all pass including `test_generate_twice_replaces_today_and_appends_history`

- [ ] **Step 6: Commit**

```bash
git add src/api/watchlists/service.py tests/unit/api/test_watchlist_service.py tests/integration/test_watchlist_eod.py
git commit -m "fix: consolidate EOD generation into WatchlistGenerationService only (LIN-68, LIN-69)

- Remove generate_from_scanner_results and 4 private EOD helpers from WatchlistService
- WatchlistGenerationService is now the single EOD class (used by main.py)
- Add integration test verifying second EOD run replaces Today, appends History

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Fix uncategorized watchlists invisible in GET /api/watchlists (LIN-70)

**Files:**
- Modify: `src/api/watchlists/service.py` (lines 467–549, `get_watchlists_grouped`)
- Modify: `tests/integration/api/test_watchlists.py`
- Modify: `tests/unit/api/test_watchlist_service.py`

- [ ] **Step 1: Write the failing integration test**

Add to `tests/integration/api/test_watchlists.py`:

```python
def test_get_watchlists_uncategorized_watchlist_is_visible(
    authenticated_client, seeded_user, db_session
):
    """GET /api/watchlists includes watchlists with no category under 'Uncategorized'."""
    from src.db.models import Watchlist

    user, _ = seeded_user

    # Create a watchlist with no category
    wl = Watchlist(
        user_id=user.id,
        name="No Category List",
        category_id=None,
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(wl)
    db_session.commit()

    resp = authenticated_client.get("/api/watchlists")
    assert resp.status_code == 200
    data = resp.json()

    uncategorized = next((g for g in data if g["category_name"] == "Uncategorized"), None)
    assert uncategorized is not None, "Uncategorized group must appear"
    assert any(w["name"] == "No Category List" for w in uncategorized["watchlists"])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/integration/api/test_watchlists.py::test_get_watchlists_uncategorized_watchlist_is_visible -v --no-header 2>&1 | tail -15
```

Expected: FAIL — no "Uncategorized" group in response

- [ ] **Step 3: Fix get_watchlists_grouped to include uncategorized watchlists**

In `src/api/watchlists/service.py`, after the `for category in categories:` loop (after the `return result` would be), add an uncategorized block. Replace the current `return result` (line 548) with:

```python
        # Include watchlists with no category under a synthetic "Uncategorized" group
        uncategorized_watchlists = (
            self.db_session.query(Watchlist)
            .filter(
                Watchlist.user_id == user_id,
                Watchlist.category_id.is_(None),
            )
            .order_by(Watchlist.created_at.desc())
            .all()
        )

        if uncategorized_watchlists:
            uncategorized_data = []
            for watchlist in uncategorized_watchlists:
                symbol_count = (
                    self.db_session.query(WatchlistSymbol)
                    .filter(WatchlistSymbol.watchlist_id == watchlist.id)
                    .count()
                )
                uncategorized_data.append(
                    {
                        "id": watchlist.id,
                        "name": watchlist.name,
                        "description": watchlist.description,
                        "symbol_count": symbol_count,
                        "created_at": watchlist.created_at,
                        "updated_at": watchlist.updated_at,
                    }
                )
            result.append(
                {
                    "category_id": None,
                    "category_name": "Uncategorized",
                    "category_icon": "",
                    "is_system": False,
                    "watchlists": uncategorized_data,
                }
            )

        return result
```

- [ ] **Step 4: Fix the unit test that accepted empty result as correct**

In `tests/unit/api/test_watchlist_service.py`, find the test around line 668 that asserts `grouped == []` for a watchlist with no category. Update it to assert the "Uncategorized" group is present:

```bash
grep -n "grouped == \[\]" tests/unit/api/test_watchlist_service.py
```

Replace the assertion in that test with:

```python
    # Watchlists with no category must appear under "Uncategorized"
    assert len(grouped) == 1
    assert grouped[0]["category_name"] == "Uncategorized"
    assert len(grouped[0]["watchlists"]) == 1
    assert grouped[0]["watchlists"][0]["name"] == "<whatever name was used in that test>"
```

(Check the exact watchlist name used in the existing test and use it.)

- [ ] **Step 5: Run tests**

```bash
python3 -m pytest tests/unit/api/test_watchlist_service.py tests/integration/api/test_watchlists.py -v --no-header 2>&1 | tail -20
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/api/watchlists/service.py tests/unit/api/test_watchlist_service.py tests/integration/api/test_watchlists.py
git commit -m "fix: include uncategorized watchlists in GET /api/watchlists (LIN-70)

- get_watchlists_grouped now appends Uncategorized group for category_id=None watchlists
- Group only appears when at least one uncategorized watchlist exists
- Fix unit test that incorrectly accepted empty result as correct

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Add is_system and sort_order to CategoryResponse (LIN-74)

**Files:**
- Modify: `src/api/watchlists/schemas.py`
- Modify: `tests/integration/api/test_watchlists_categories_and_clone.py`

- [ ] **Step 1: Write the failing test**

In `tests/integration/api/test_watchlists_categories_and_clone.py`, the existing `test_get_categories_returns_all_user_categories` checks the response structure. Add assertions for the two new fields at the end of that test, or add a dedicated test:

```python
def test_get_categories_response_includes_is_system_and_sort_order(
    authenticated_client, seeded_watchlist_data
):
    """GET /api/watchlists/categories includes is_system and sort_order fields."""
    resp = authenticated_client.get("/api/watchlists/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0

    # All categories must expose is_system and sort_order
    for cat in data:
        assert "is_system" in cat, "CategoryResponse must include is_system"
        assert "sort_order" in cat, "CategoryResponse must include sort_order"

    # Verify values are correct for known categories
    active = next(c for c in data if c["name"] == "Active Trading")
    assert active["is_system"] is True
    assert active["sort_order"] == 1

    custom = next(c for c in data if c["name"] == "Custom Category")
    assert custom["is_system"] is False
    assert custom["sort_order"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/integration/api/test_watchlists_categories_and_clone.py::test_get_categories_response_includes_is_system_and_sort_order -v --no-header 2>&1 | tail -15
```

Expected: FAIL — `is_system` and `sort_order` not in response

- [ ] **Step 3: Add fields to CategoryResponse schema**

In `src/api/watchlists/schemas.py`, replace the `CategoryResponse` class (lines 80–91):

```python
class CategoryResponse(BaseModel):
    """Schema for category response."""

    id: int
    name: str
    description: Optional[str]
    color: Optional[str]
    icon: Optional[str]
    is_system: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/integration/api/test_watchlists_categories_and_clone.py -v --no-header 2>&1 | tail -20
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/api/watchlists/schemas.py tests/integration/api/test_watchlists_categories_and_clone.py
git commit -m "fix: expose is_system and sort_order in CategoryResponse (LIN-74)

Allows frontend to distinguish system from user categories without
attempting a DELETE to discover protection status.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Fix clone endpoint category ownership validation (LIN-71)

**Files:**
- Modify: `src/api/watchlists/routes.py` (lines 533–539, clone_watchlist)
- Modify: `tests/integration/api/test_watchlists_categories_and_clone.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/api/test_watchlists_categories_and_clone.py`:

```python
def test_clone_watchlist_with_other_users_category_returns_400(
    authenticated_client, seeded_watchlist_data, db_session
):
    """POST /api/watchlists/{id}/clone returns 400 when category_id belongs to another user."""
    from src.api.auth import hash_password
    from src.db.models import User, WatchlistCategory

    watchlists = seeded_watchlist_data["watchlists"]
    original_watchlist = watchlists[0]

    # Create another user with their own category
    other_user = User(id=99, username="otheruser2", password_hash=hash_password("pass123"))
    db_session.add(other_user)
    other_cat = WatchlistCategory(
        user_id=other_user.id,
        name="Private Category",
        is_system=False,
        sort_order=1,
    )
    db_session.add(other_cat)
    db_session.commit()

    # Try to clone and assign to another user's category
    resp = authenticated_client.post(
        f"/api/watchlists/{original_watchlist.id}/clone",
        json={"name": "Stolen Clone", "category_id": other_cat.id},
    )
    assert resp.status_code == 400
    assert "invalid category_id" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/integration/api/test_watchlists_categories_and_clone.py::test_clone_watchlist_with_other_users_category_returns_400 -v --no-header 2>&1 | tail -15
```

Expected: FAIL — currently returns 201 (no ownership check)

- [ ] **Step 3: Add ownership validation to clone route**

In `src/api/watchlists/routes.py`, replace the "Apply optional overrides" block (lines 533–539):

```python
    # Apply optional overrides (with ownership validation)
    if clone_data.category_id is not None:
        category = db.get(WatchlistCategory, clone_data.category_id)
        if not category or category.user_id != user.id:
            # Rollback the clone before raising
            db.delete(cloned_watchlist)
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="Invalid category_id",
            )
        cloned_watchlist.category_id = clone_data.category_id  # type: ignore[assignment]
    if clone_data.description is not None:
        cloned_watchlist.description = clone_data.description  # type: ignore[assignment]
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/integration/api/test_watchlists_categories_and_clone.py -v --no-header 2>&1 | tail -20
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/api/watchlists/routes.py tests/integration/api/test_watchlists_categories_and_clone.py
git commit -m "fix: validate category ownership in clone endpoint (LIN-71)

Clone route now rejects category_id values belonging to other users,
matching the ownership check already present in create and update routes.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Fix update_watchlist to allow clearing category_id (LIN-72)

**Files:**
- Modify: `src/api/watchlists/routes.py` (line 244)
- Modify: `src/api/watchlists/service.py` (line 114)
- Modify: `tests/integration/api/test_watchlists.py`

**Context:** `PUT /api/watchlists/{id}` with `{"category_id": null}` must clear the category. Currently `exclude_none=True` on the route and `value is not None` in the service both silently swallow the null. Fix: use `exclude_unset=True` (only include fields the caller actually sent) and remove the `is not None` guard for `category_id`.

- [ ] **Step 1: Write the failing integration test**

Add to `tests/integration/api/test_watchlists.py`:

```python
def test_update_watchlist_can_clear_category_id(
    authenticated_client, seeded_user, db_session
):
    """PUT /api/watchlists/{id} with category_id=null clears the category."""
    from src.db.models import Watchlist, WatchlistCategory

    user, _ = seeded_user

    # Create a category and a watchlist assigned to it
    cat = WatchlistCategory(
        user_id=user.id, name="Temp Cat", is_system=False, sort_order=1
    )
    db_session.add(cat)
    db_session.commit()

    wl = Watchlist(
        user_id=user.id,
        name="Categorized List",
        category_id=cat.id,
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(wl)
    db_session.commit()

    # Clear the category
    resp = authenticated_client.put(
        f"/api/watchlists/{wl.id}",
        json={"category_id": None},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["category_id"] is None

    # Verify in DB
    db_session.expire_all()
    updated = db_session.get(Watchlist, wl.id)
    assert updated.category_id is None


def test_update_watchlist_partial_update_name_only_preserves_category(
    authenticated_client, seeded_user, db_session
):
    """PUT /api/watchlists/{id} with name only does not clear category_id."""
    from src.db.models import Watchlist, WatchlistCategory

    user, _ = seeded_user

    cat = WatchlistCategory(
        user_id=user.id, name="Keep Cat", is_system=False, sort_order=1
    )
    db_session.add(cat)
    db_session.commit()

    wl = Watchlist(
        user_id=user.id,
        name="Original Name",
        category_id=cat.id,
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(wl)
    db_session.commit()

    # Update name only (category_id not in payload at all)
    resp = authenticated_client.put(
        f"/api/watchlists/{wl.id}",
        json={"name": "New Name"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["category_id"] == cat.id  # Must be preserved
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/integration/api/test_watchlists.py::test_update_watchlist_can_clear_category_id tests/integration/api/test_watchlists.py::test_update_watchlist_partial_update_name_only_preserves_category -v --no-header 2>&1 | tail -15
```

Expected: first test FAILS (category not cleared), second test may pass or fail

- [ ] **Step 3: Fix the route — use exclude_unset=True**

In `src/api/watchlists/routes.py`, line 244, change:

```python
    update_data = payload.model_dump(exclude_none=True)
```

to:

```python
    update_data = payload.model_dump(exclude_unset=True)
```

- [ ] **Step 4: Fix the service — allow None for category_id**

In `src/api/watchlists/service.py`, replace lines 112–115:

```python
        # Update only allowed fields
        allowed_fields = {"name", "description", "category_id"}
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                setattr(watchlist, field, value)
```

with:

```python
        # Update only allowed fields; category_id explicitly allows None (to unassign)
        allowed_fields = {"name", "description", "category_id"}
        for field, value in kwargs.items():
            if field not in allowed_fields:
                continue
            if field == "category_id" or value is not None:
                setattr(watchlist, field, value)
```

- [ ] **Step 5: Run tests**

```bash
python3 -m pytest tests/integration/api/test_watchlists.py -v --no-header 2>&1 | tail -20
```

Expected: all pass including the two new tests

- [ ] **Step 6: Commit**

```bash
git add src/api/watchlists/routes.py src/api/watchlists/service.py tests/integration/api/test_watchlists.py
git commit -m "fix: allow clearing category_id via PUT /api/watchlists/{id} (LIN-72)

- Route uses exclude_unset=True so explicitly-sent null passes through
- Service allows setting category_id to None (unassign from category)
- Absent fields in partial updates still preserve existing values

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Fix get_or_create_default_categories strict equality (LIN-73)

**Files:**
- Modify: `src/api/watchlists/service.py` (line 361)
- Modify: `tests/unit/api/test_watchlist_service.py`

- [ ] **Step 1: Write the failing unit test**

Add to `tests/unit/api/test_watchlist_service.py`:

```python
def test_get_or_create_default_categories_with_five_system_categories_no_error(
    db_session,
):
    """get_or_create_default_categories does not crash when user has 5+ system categories."""
    from src.db.models import User, WatchlistCategory
    from src.api.watchlists.service import WatchlistService

    user = User(username="cat5user", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    # Create 5 system categories (4 defaults + 1 extra)
    names = ["Active Trading", "Scanner Results", "Research", "Archived", "Extra System"]
    for i, name in enumerate(names, 1):
        cat = WatchlistCategory(
            user_id=user.id,
            name=name,
            is_system=True,
            sort_order=i,
        )
        db_session.add(cat)
    db_session.commit()

    svc = WatchlistService(db_session)
    # Must not raise IntegrityError
    result = svc.get_or_create_default_categories(cast(int, user.id))
    assert len(result) >= 4
```

(Add `from typing import cast` at top of file if not already present.)

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest "tests/unit/api/test_watchlist_service.py::test_get_or_create_default_categories_with_five_system_categories_no_error" -v --no-header 2>&1 | tail -15
```

Expected: FAIL with `IntegrityError` or `AssertionError`

- [ ] **Step 3: Fix the equality check**

In `src/api/watchlists/service.py`, line 361, change:

```python
        if len(existing_categories) == 4:
```

to:

```python
        if len(existing_categories) >= len(defaults):
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/unit/api/test_watchlist_service.py -v --no-header 2>&1 | tail -20
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/api/watchlists/service.py tests/unit/api/test_watchlist_service.py
git commit -m "fix: use >= len(defaults) in get_or_create_default_categories (LIN-73)

Prevents IntegrityError when user has more system categories than the
current default count, e.g. after a future migration adds a 5th default.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Remove .bak/.backup files and add logs/ to .gitignore (LIN-75)

**Files:**
- Delete: `src/api/watchlists/routes.py.backup`
- Delete: `src/api/watchlists/routes.py.bak`
- Modify: `.gitignore`
- Untrack: `logs/`

- [ ] **Step 1: Delete artifact files**

```bash
rm src/api/watchlists/routes.py.backup src/api/watchlists/routes.py.bak
```

- [ ] **Step 2: Untrack logs directory**

```bash
git rm --cached logs/ -r 2>/dev/null || echo "logs/ not tracked"
```

- [ ] **Step 3: Update .gitignore**

Add to the bottom of `.gitignore`:

```
# Editor artifacts
*.bak
*.backup

# Runtime logs
logs/
```

- [ ] **Step 4: Run tests to verify nothing broken**

```bash
python3 -m pytest tests/unit/ -q --no-header 2>&1 | tail -5
```

Expected: 171+ passed

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git rm --cached src/api/watchlists/routes.py.backup src/api/watchlists/routes.py.bak 2>/dev/null
git commit -m "chore: remove .bak/.backup artifacts, add logs/ and *.bak to .gitignore (LIN-75)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Final: Run full test suite and verify CI-clean

- [ ] **Run all unit tests**

```bash
python3 -m pytest tests/unit/ -q --no-header 2>&1 | tail -5
```

Expected: all pass

- [ ] **Run ruff and black checks**

```bash
ruff check src/ tests/ && black --check . 2>&1 | tail -5
```

Expected: no errors

- [ ] **Run mypy**

```bash
mypy src/ --ignore-missing-imports 2>&1 | tail -10
```

Expected: no new errors

- [ ] **Push branch and update PR**

```bash
git push -u origin fix/pr15-review-fixes
```
