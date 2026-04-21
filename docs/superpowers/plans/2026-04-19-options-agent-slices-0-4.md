# Options Agent — Slices 0–4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational options agent module: scaffolding, IVR computation, Dolthub chain ingestion, real-IV upgrade, and market regime detection.

**Architecture:** Embedded module `src/options_agent/` inside the existing market-data repo. Reuses PostgreSQL, SQLAlchemy, APScheduler, and FastAPI. Dolthub options data is served via `dolt sql-server` on localhost:3307 (MySQL protocol). Each slice is a hard stop — run `make ci` and get human sign-off before starting the next.

**Tech Stack:** Python, SQLAlchemy, Alembic, FastAPI, numpy, pandas, pymysql, freezegun, pytest/testcontainers

---

## File Map

**Created:**
```
src/options_agent/__init__.py
src/options_agent/config.py
src/options_agent/cli.py
src/options_agent/ivr.py
src/options_agent/data/__init__.py
src/options_agent/data/dolt_client.py
src/options_agent/data/chain_ingester.py
src/options_agent/data/expiries.py
src/options_agent/signals/__init__.py
src/options_agent/signals/regime.py
src/options_agent/chain/__init__.py
src/options_agent/targets/__init__.py
src/options_agent/candidates/__init__.py
tests/options_agent/__init__.py
tests/options_agent/conftest.py
tests/options_agent/unit/__init__.py
tests/options_agent/unit/test_module_imports.py
tests/options_agent/unit/test_ivr.py
tests/options_agent/unit/test_expiries.py
tests/options_agent/unit/test_regime_detector.py
tests/options_agent/integration/__init__.py
tests/options_agent/integration/test_dolt_ingest.py
tests/options_agent/api/__init__.py
tests/options_agent/api/test_ivr_routes.py
tests/options_agent/fixtures/bars/  (directory)
tests/options_agent/fixtures/chains/ (directory)
src/db/migrations/versions/20260419_0001_add_options_ivr_snapshots.py
src/db/migrations/versions/20260419_0002_add_options_eod_chains.py
src/db/migrations/versions/20260419_0003_add_regime_snapshots.py
config/options_agent/filters.yaml
```

**Modified:**
```
pyproject.toml               — add pymysql, scipy, freezegun, anthropic
src/config.py                — add DOLT_OPTIONS_URL, DOLT_REPO_PATH, ANTHROPIC_API_KEY
src/db/models.py             — add IVRSnapshot, OptionsEodChain, RegimeSnapshot ORM models
src/api/main.py              — register /api/options router
src/data_fetcher/scheduler.py — add 03:00/03:15/03:30 ET nightly jobs
frontend/src/pages/watchlists/symbol-row.tsx — IVR badge + regime pill
```

---

## Task 1: Add dependencies and env config

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/config.py`

- [ ] **Step 1: Add new Python deps to pyproject.toml**

In `pyproject.toml` under `dependencies = [`:
```toml
    "pymysql>=1.1.0",
    "scipy>=1.12.0",
    "anthropic>=0.40.0",
```
Under `dev = [`:
```toml
    "freezegun>=1.5.0",
```

- [ ] **Step 2: Install**
```bash
pip install -e ".[dev]"
```
Expected: installs pymysql, scipy, anthropic, freezegun without errors.

- [ ] **Step 3: Extend src/config.py**

Add to the `Config.__init__` body after `self.API_RATE_LIMIT_DELAY`:
```python
        # Options agent
        self.DOLT_OPTIONS_URL = os.getenv(
            "DOLT_OPTIONS_URL", "mysql+pymysql://root@localhost:3307/options"
        )
        self.DOLT_REPO_PATH = os.getenv("DOLT_REPO_PATH", "/var/lib/dolt-options")
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        self.OPTIONS_AGENT_LLM_MODEL = os.getenv(
            "OPTIONS_AGENT_LLM_MODEL", "claude-haiku-4-5-20251001"
        )
```

- [ ] **Step 4: Verify config loads**
```bash
python -c "from src.config import get_config; get_config.cache_clear(); c = get_config(); print(c.DOLT_OPTIONS_URL)"
```
Expected: prints `mysql+pymysql://root@localhost:3307/options`

- [ ] **Step 5: Commit**
```bash
git add pyproject.toml src/config.py
git commit -m "chore(options-agent): add deps and env config"
```

---

## Task 2: Slice 0 — Module scaffolding

**Files:**
- Create: `src/options_agent/__init__.py`
- Create: `src/options_agent/config.py`
- Create: `src/options_agent/cli.py`
- Create: `src/options_agent/data/__init__.py`
- Create: `src/options_agent/signals/__init__.py`
- Create: `src/options_agent/chain/__init__.py`
- Create: `src/options_agent/targets/__init__.py`
- Create: `src/options_agent/candidates/__init__.py`
- Create: `tests/options_agent/__init__.py`
- Create: `tests/options_agent/unit/__init__.py`
- Create: `tests/options_agent/unit/test_module_imports.py`

- [ ] **Step 1: Write failing import tests**

`tests/options_agent/unit/test_module_imports.py`:
```python
def test_module_version():
    from src.options_agent import __version__
    assert __version__ == "0.1.0"

def test_submodules_importable():
    import src.options_agent.data
    import src.options_agent.signals
    import src.options_agent.chain
    import src.options_agent.targets
    import src.options_agent.candidates
```

- [ ] **Step 2: Run — confirm fail**
```bash
pytest tests/options_agent/unit/test_module_imports.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create module files**

`src/options_agent/__init__.py`:
```python
__version__ = "0.1.0"
```

`src/options_agent/config.py`:
```python
from dataclasses import dataclass
from src.config import get_config


@dataclass
class OptionsAgentConfig:
    dolt_options_url: str
    dolt_repo_path: str
    llm_model: str
    anthropic_api_key: str | None


def get_options_config() -> OptionsAgentConfig:
    cfg = get_config()
    return OptionsAgentConfig(
        dolt_options_url=cfg.DOLT_OPTIONS_URL,
        dolt_repo_path=cfg.DOLT_REPO_PATH,
        llm_model=cfg.OPTIONS_AGENT_LLM_MODEL,
        anthropic_api_key=cfg.ANTHROPIC_API_KEY,
    )
```

`src/options_agent/cli.py`:
```python
import click


@click.group()
def options_cli():
    """Options agent CLI commands."""
    pass
```

`src/options_agent/data/__init__.py`: (empty)
`src/options_agent/signals/__init__.py`: (empty)
`src/options_agent/chain/__init__.py`: (empty)
`src/options_agent/targets/__init__.py`: (empty)
`src/options_agent/candidates/__init__.py`: (empty)
`tests/options_agent/__init__.py`: (empty)
`tests/options_agent/unit/__init__.py`: (empty)

- [ ] **Step 4: Run — confirm pass**
```bash
pytest tests/options_agent/unit/test_module_imports.py -v
```
Expected: 2 tests PASS

- [ ] **Step 5: Run full CI**
```bash
make ci
```
Expected: all green

- [ ] **Step 6: Commit**
```bash
git add src/options_agent/ tests/options_agent/ config/
git commit -m "feat(options-agent): slice 0 - module scaffolding"
```

---

## Task 3: Slice 1 — IVR models and migration

**Files:**
- Modify: `src/db/models.py`
- Create: `src/db/migrations/versions/20260419_0001_add_options_ivr_snapshots.py`

- [ ] **Step 1: Add IVRSnapshot ORM model to src/db/models.py**

At the end of `src/db/models.py`:
```python
class IVRSnapshot(Base):
    """IV Rank snapshots — one row per symbol per date per calculation basis."""

    __tablename__ = "ivr_snapshots"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(16), ForeignKey("stocks.symbol"), nullable=False)
    as_of_date = Column(DateTime, nullable=False)
    ivr = Column(NUMERIC(5, 2), nullable=False)
    current_hv = Column(NUMERIC(8, 4), nullable=False)
    calculation_basis = Column(String(16), nullable=False)  # "hv_proxy" | "implied"
    computed_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "symbol", "as_of_date", "calculation_basis", name="uq_ivr_symbol_date_basis"
        ),
        Index("ix_ivr_symbol", "symbol"),
        Index("ix_ivr_as_of", "as_of_date"),
    )
```

- [ ] **Step 2: Generate migration**
```bash
alembic revision --autogenerate -m "add_ivr_snapshots"
```
Then rename the generated file to `20260419_0001_add_ivr_snapshots.py` and verify the upgrade/downgrade SQL looks correct.

- [ ] **Step 3: Apply migration**
```bash
alembic upgrade head
```
Expected: no errors

- [ ] **Step 4: Commit**
```bash
git add src/db/models.py src/db/migrations/versions/
git commit -m "feat(options-agent): add IVRSnapshot model and migration"
```

---

## Task 4: Slice 1 — IVR computation (HV proxy)

**Files:**
- Create: `src/options_agent/ivr.py`
- Create: `tests/options_agent/unit/test_ivr.py`
- Create: `tests/options_agent/fixtures/bars/` (synthetic helpers in conftest)
- Create: `tests/options_agent/conftest.py`

- [ ] **Step 1: Write fixture helpers and failing tests**

`tests/options_agent/conftest.py`:
```python
import numpy as np
import pandas as pd
from datetime import date, timedelta


def _make_bars(closes: list[float]) -> pd.DataFrame:
    n = len(closes)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
    return pd.DataFrame({"close": closes, "date": dates})


def synthetic_bars_rising_volatility(n: int = 300) -> pd.DataFrame:
    """Closes that produce increasing realised volatility over time."""
    rng = np.random.default_rng(42)
    # First 252 bars: low vol; last 48 bars: high vol
    low_vol = np.cumprod(1 + rng.normal(0, 0.005, 252)) * 100
    high_vol = np.cumprod(1 + rng.normal(0, 0.04, 48)) * low_vol[-1]
    closes = np.concatenate([low_vol, high_vol]).tolist()
    return _make_bars(closes)


def synthetic_bars_falling_volatility(n: int = 300) -> pd.DataFrame:
    """Closes that produce decreasing realised volatility over time."""
    rng = np.random.default_rng(7)
    high_vol = np.cumprod(1 + rng.normal(0, 0.04, 252)) * 100
    low_vol = np.cumprod(1 + rng.normal(0, 0.001, 48)) * high_vol[-1]
    closes = np.concatenate([high_vol, low_vol]).tolist()
    return _make_bars(closes)


def synthetic_bars_flat(n: int = 300) -> pd.DataFrame:
    closes = [100.0] * n
    return _make_bars(closes)
```

`tests/options_agent/unit/test_ivr.py`:
```python
import pytest
from tests.options_agent.conftest import (
    synthetic_bars_rising_volatility,
    synthetic_bars_falling_volatility,
    _make_bars,
)


def test_ivr_returns_percentile_in_range():
    from src.options_agent.ivr import compute_ivr_from_hv
    bars = synthetic_bars_rising_volatility()
    result = compute_ivr_from_hv(bars, window=20, lookback=252)
    assert 0 <= result.ivr <= 100
    assert result.calculation_basis == "hv_proxy"


def test_ivr_at_current_high_is_100():
    from src.options_agent.ivr import compute_ivr_from_hv
    bars = synthetic_bars_rising_volatility()
    result = compute_ivr_from_hv(bars, window=20, lookback=252)
    assert result.ivr == pytest.approx(100.0, abs=1.0)


def test_ivr_at_current_low_is_0():
    from src.options_agent.ivr import compute_ivr_from_hv
    bars = synthetic_bars_falling_volatility()
    result = compute_ivr_from_hv(bars, window=20, lookback=252)
    assert result.ivr == pytest.approx(0.0, abs=1.0)


def test_ivr_insufficient_history_raises():
    from src.options_agent.ivr import compute_ivr_from_hv, InsufficientHistoryError
    bars = _make_bars([100.0] * 50)
    with pytest.raises(InsufficientHistoryError):
        compute_ivr_from_hv(bars, window=20, lookback=252)


def test_ivr_result_fields():
    from src.options_agent.ivr import compute_ivr_from_hv
    bars = synthetic_bars_rising_volatility()
    result = compute_ivr_from_hv(bars, window=20, lookback=252)
    assert result.current_hv > 0
    assert result.hv_min >= 0
    assert result.hv_max >= result.hv_min
    assert result.as_of is not None
```

- [ ] **Step 2: Run — confirm fail**
```bash
pytest tests/options_agent/unit/test_ivr.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.options_agent.ivr'`

- [ ] **Step 3: Implement src/options_agent/ivr.py**

```python
"""IVR (Implied Volatility Rank) computation using HV as proxy."""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


class InsufficientHistoryError(ValueError):
    pass


@dataclass
class IVRResult:
    ivr: float
    current_hv: float
    hv_min: float
    hv_max: float
    calculation_basis: str
    as_of: date


def compute_ivr_from_hv(
    bars: pd.DataFrame,
    window: int = 20,
    lookback: int = 252,
) -> IVRResult:
    """Compute IV Rank using historical volatility as a proxy.

    Args:
        bars: DataFrame with 'close' column, sorted oldest-first.
        window: rolling window for HV computation (trading days).
        lookback: number of HV values to rank against.
    """
    closes = bars["close"].astype(float).values
    if len(closes) < window + lookback:
        raise InsufficientHistoryError(
            f"Need at least {window + lookback} bars, got {len(closes)}"
        )

    log_returns = np.log(closes[1:] / closes[:-1])
    hv_series = pd.Series(log_returns).rolling(window).std().dropna() * np.sqrt(252)
    hv_values = hv_series.values

    if len(hv_values) < lookback:
        raise InsufficientHistoryError(
            f"Need at least {lookback} HV values, got {len(hv_values)}"
        )

    history = hv_values[-lookback:]
    current = hv_values[-1]
    hv_min = float(history.min())
    hv_max = float(history.max())

    if hv_max == hv_min:
        ivr = 0.0
    else:
        ivr = float((current - hv_min) / (hv_max - hv_min) * 100)

    as_of_val = bars["date"].iloc[-1] if "date" in bars.columns else date.today()

    return IVRResult(
        ivr=round(ivr, 2),
        current_hv=round(float(current), 4),
        hv_min=round(hv_min, 4),
        hv_max=round(hv_max, 4),
        calculation_basis="hv_proxy",
        as_of=as_of_val,
    )
```

- [ ] **Step 4: Run — confirm pass**
```bash
pytest tests/options_agent/unit/test_ivr.py -v
```
Expected: 5 tests PASS

- [ ] **Step 5: Commit**
```bash
git add src/options_agent/ivr.py tests/options_agent/unit/test_ivr.py tests/options_agent/conftest.py
git commit -m "feat(options-agent): slice 1 - IVR HV proxy computation"
```

---

## Task 5: Slice 1 — IVR persistence and API

**Files:**
- Create: `src/api/options/__init__.py`
- Create: `src/api/options/routes.py`
- Create: `src/api/options/schemas.py`
- Modify: `src/api/main.py`
- Create: `tests/options_agent/api/__init__.py`
- Create: `tests/options_agent/api/test_ivr_routes.py`
- Create: `tests/options_agent/integration/__init__.py`
- Create: `tests/options_agent/integration/test_ivr_persistence.py`

- [ ] **Step 1: Write API tests**

`tests/options_agent/api/test_ivr_routes.py`:
```python
import pytest
from datetime import date
from freezegun import freeze_time
from httpx import AsyncClient


@pytest.fixture
def seed_ivr(db_session):
    from src.db.models import IVRSnapshot
    from datetime import datetime, timezone
    snap = IVRSnapshot(
        symbol="AAPL",
        as_of_date=date(2026, 4, 18),
        ivr=34.5,
        current_hv=0.2312,
        calculation_basis="hv_proxy",
        computed_at=datetime.now(timezone.utc),
    )
    db_session.add(snap)
    db_session.commit()
    return snap


def test_get_ivr_for_symbol(client, seed_ivr):
    resp = client.get("/api/options/ivr/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert 0 <= body["ivr"] <= 100
    assert body["calculation_basis"] in ("hv_proxy", "implied")


def test_get_ivr_unknown_symbol_404(client):
    resp = client.get("/api/options/ivr/ZZZZ")
    assert resp.status_code == 404


def test_get_ivr_bulk(client, seed_ivr):
    resp = client.get("/api/options/ivr?symbols=AAPL")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) == 1
```

`tests/options_agent/integration/test_ivr_persistence.py`:
```python
from datetime import date


def test_compute_and_store_ivr(db_session):
    from tests.options_agent.conftest import synthetic_bars_rising_volatility
    from src.options_agent.ivr import compute_and_store_ivr
    from src.db.models import IVRSnapshot

    bars = synthetic_bars_rising_volatility()
    result = compute_and_store_ivr(db_session, "AAPL", bars, as_of=date(2026, 4, 18))

    stored = (
        db_session.query(IVRSnapshot)
        .filter_by(symbol="AAPL", calculation_basis="hv_proxy")
        .one()
    )
    assert stored.ivr == result.ivr


def test_compute_and_store_ivr_upserts(db_session):
    from tests.options_agent.conftest import synthetic_bars_rising_volatility
    from src.options_agent.ivr import compute_and_store_ivr
    from src.db.models import IVRSnapshot

    bars = synthetic_bars_rising_volatility()
    compute_and_store_ivr(db_session, "AAPL", bars, as_of=date(2026, 4, 18))
    compute_and_store_ivr(db_session, "AAPL", bars, as_of=date(2026, 4, 18))
    count = db_session.query(IVRSnapshot).filter_by(symbol="AAPL").count()
    assert count == 1
```

- [ ] **Step 2: Run — confirm fail**
```bash
pytest tests/options_agent/api/test_ivr_routes.py tests/options_agent/integration/test_ivr_persistence.py -v
```
Expected: ImportError / 404 failures

- [ ] **Step 3: Add compute_and_store_ivr to src/options_agent/ivr.py**

Append to `src/options_agent/ivr.py`:
```python
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert


def compute_and_store_ivr(
    session: Session,
    symbol: str,
    bars: pd.DataFrame,
    as_of: date,
    window: int = 20,
    lookback: int = 252,
) -> IVRResult:
    from src.db.models import IVRSnapshot

    result = compute_ivr_from_hv(bars, window=window, lookback=lookback)
    stmt = pg_insert(IVRSnapshot).values(
        symbol=symbol,
        as_of_date=as_of,
        ivr=result.ivr,
        current_hv=result.current_hv,
        calculation_basis=result.calculation_basis,
        computed_at=datetime.now(timezone.utc),
    ).on_conflict_do_update(
        constraint="uq_ivr_symbol_date_basis",
        set_={"ivr": result.ivr, "current_hv": result.current_hv,
              "computed_at": datetime.now(timezone.utc)},
    )
    session.execute(stmt)
    session.commit()
    return result
```

- [ ] **Step 4: Create API route files**

`src/api/options/__init__.py`: (empty)

`src/api/options/schemas.py`:
```python
from pydantic import BaseModel
from datetime import date


class IVRResponse(BaseModel):
    symbol: str
    ivr: float
    current_hv: float
    calculation_basis: str
    as_of_date: date
```

`src/api/options/routes.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.options.schemas import IVRResponse
from src.db.models import IVRSnapshot

router = APIRouter()


@router.get("/ivr/{symbol}", response_model=IVRResponse)
def get_ivr(symbol: str, db: Session = Depends(get_db)):
    snap = (
        db.query(IVRSnapshot)
        .filter_by(symbol=symbol.upper())
        .order_by(IVRSnapshot.as_of_date.desc())
        .first()
    )
    if not snap:
        raise HTTPException(status_code=404, detail=f"No IVR data for {symbol}")
    return IVRResponse(
        symbol=snap.symbol,
        ivr=float(snap.ivr),
        current_hv=float(snap.current_hv),
        calculation_basis=snap.calculation_basis,
        as_of_date=snap.as_of_date,
    )


@router.get("/ivr", response_model=list[IVRResponse])
def get_ivr_bulk(symbols: str = Query(...), db: Session = Depends(get_db)):
    syms = [s.strip().upper() for s in symbols.split(",")]
    snaps = db.query(IVRSnapshot).filter(IVRSnapshot.symbol.in_(syms)).all()
    return [
        IVRResponse(
            symbol=s.symbol,
            ivr=float(s.ivr),
            current_hv=float(s.current_hv),
            calculation_basis=s.calculation_basis,
            as_of_date=s.as_of_date,
        )
        for s in snaps
    ]
```

- [ ] **Step 5: Register options router in src/api/main.py**

Add import and include_router after the existing routers:
```python
from src.api.options.routes import router as options_router
# ...in the app factory, after other include_router calls:
app.include_router(options_router, prefix="/api/options", tags=["options"])
```

- [ ] **Step 6: Add `client` fixture to tests/options_agent/conftest.py**

```python
import pytest
from httpx import TestClient


@pytest.fixture
def client(postgres_container):
    from src.api.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 7: Run — confirm pass**
```bash
pytest tests/options_agent/api/ tests/options_agent/integration/test_ivr_persistence.py -v
```
Expected: all PASS

- [ ] **Step 8: Run make ci**
```bash
make ci
```
Expected: green

- [ ] **Step 9: Commit**
```bash
git add src/api/options/ src/options_agent/ivr.py tests/options_agent/
git commit -m "feat(options-agent): slice 1 - IVR API and persistence"
```

---

## Task 6: Slice 1 — IVR badge in watchlist symbol row

**Files:**
- Modify: `frontend/src/pages/watchlists/symbol-row.tsx`
- Modify: `frontend/src/lib/watchlists-api.ts` (add IVR fetch)
- Create: `frontend/src/lib/options-api.ts`

- [ ] **Step 1: Create options-api.ts**

`frontend/src/lib/options-api.ts`:
```typescript
import { apiFetch } from "./api";

export interface IVRData {
  symbol: string;
  ivr: number;
  current_hv: number;
  calculation_basis: string;
  as_of_date: string;
}

export const optionsAPI = {
  getIVR: (symbol: string): Promise<IVRData> =>
    apiFetch(`/api/options/ivr/${symbol}`),

  getIVRBulk: (symbols: string[]): Promise<IVRData[]> =>
    apiFetch(`/api/options/ivr?symbols=${symbols.join(",")}`),
};
```

- [ ] **Step 2: Add IVR badge to symbol-row.tsx**

In `frontend/src/pages/watchlists/symbol-row.tsx`, import and add IVR resource:

```typescript
import { createResource } from "solid-js";
import { optionsAPI, type IVRData } from "../../lib/options-api";

// Inside the component, after existing signals:
const [ivr] = createResource<IVRData | null>(
  () => props.symbol,
  async (sym) => {
    try { return await optionsAPI.getIVR(sym); }
    catch { return null; }
  }
);

function ivrColor(val: number): string {
  if (val < 30) return "bg-green-100 text-green-800";
  if (val <= 70) return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
}
```

In the JSX, add the IVR badge cell alongside the existing price cells:
```tsx
<Show when={ivr()} fallback={<td class="px-2 py-1 text-xs text-gray-400">—</td>}>
  {(data) => (
    <td class="px-2 py-1">
      <span
        class={`text-xs font-medium px-1.5 py-0.5 rounded ${ivrColor(data().ivr)}`}
        title="Implied Volatility Rank — low = cheap premium, high = expensive"
      >
        IVR {Math.round(data().ivr)}
      </span>
    </td>
  )}
</Show>
```

- [ ] **Step 3: Build frontend and verify no TS errors**
```bash
cd frontend && npm run build
```
Expected: no errors

- [ ] **Step 4: Commit**
```bash
git add frontend/src/lib/options-api.ts frontend/src/pages/watchlists/symbol-row.tsx
git commit -m "feat(options-agent): slice 1 - IVR badge in watchlist symbol row"
```

**SLICE 1 CHECKPOINT** — run `make ci`, open watchlist in browser and confirm IVR badge appears. Human sign-off required before Task 7.

---

## Task 7: Slice 2 — Dolthub client and expiry calculation

**Files:**
- Create: `src/options_agent/data/dolt_client.py`
- Create: `src/options_agent/data/expiries.py`
- Create: `tests/options_agent/unit/test_expiries.py`

- [ ] **Step 1: Write expiry unit tests**

`tests/options_agent/unit/test_expiries.py`:
```python
from datetime import date
from freezegun import freeze_time


@freeze_time("2026-04-20")  # Monday
def test_expiries_from_monday():
    from src.options_agent.data.expiries import determine_target_expiries
    buckets = determine_target_expiries(as_of=date(2026, 4, 20))
    assert len(buckets) == 3
    assert buckets[0].label == "current_week"
    assert buckets[1].label == "next_week"
    assert buckets[2].label == "monthly"
    # current week friday
    assert buckets[0].expiry == date(2026, 4, 24)
    # next week friday
    assert buckets[1].expiry == date(2026, 5, 1)


@freeze_time("2026-04-23")  # Thursday — current week is imminent
def test_expiries_from_thursday_skips_current_week():
    from src.options_agent.data.expiries import determine_target_expiries
    buckets = determine_target_expiries(as_of=date(2026, 4, 23))
    # On Thursday, current week expiry is tomorrow — still valid
    assert buckets[0].label == "current_week"
    assert buckets[0].expiry == date(2026, 4, 24)


def test_monthly_is_third_friday():
    from src.options_agent.data.expiries import determine_target_expiries
    # May 2026: 3rd Friday is May 15
    buckets = determine_target_expiries(as_of=date(2026, 4, 20))
    monthly = next(b for b in buckets if b.label == "monthly")
    assert monthly.expiry == date(2026, 5, 15)
```

- [ ] **Step 2: Run — confirm fail**
```bash
pytest tests/options_agent/unit/test_expiries.py -v
```
Expected: ImportError

- [ ] **Step 3: Implement expiries.py**

`src/options_agent/data/expiries.py`:
```python
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class ExpiryBucket:
    label: str  # "current_week" | "next_week" | "monthly"
    expiry: date


def _next_friday(d: date) -> date:
    days_ahead = 4 - d.weekday()  # Friday is weekday 4
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def _third_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    # weekday of first day; Friday=4
    first_friday = first + timedelta(days=(4 - first.weekday()) % 7)
    return first_friday + timedelta(weeks=2)


def determine_target_expiries(as_of: date) -> list[ExpiryBucket]:
    current_week_fri = _next_friday(as_of)

    next_week_start = current_week_fri + timedelta(days=3)  # Monday after
    next_week_fri = _next_friday(next_week_start)

    # Nearest monthly from current_week_fri forward
    year, month = as_of.year, as_of.month
    monthly = _third_friday(year, month)
    if monthly <= as_of:
        month += 1
        if month > 12:
            month = 1
            year += 1
        monthly = _third_friday(year, month)

    return [
        ExpiryBucket(label="current_week", expiry=current_week_fri),
        ExpiryBucket(label="next_week", expiry=next_week_fri),
        ExpiryBucket(label="monthly", expiry=monthly),
    ]
```

- [ ] **Step 4: Run — confirm pass**
```bash
pytest tests/options_agent/unit/test_expiries.py -v
```
Expected: all PASS

- [ ] **Step 5: Implement dolt_client.py**

`src/options_agent/data/dolt_client.py`:
```python
"""Client for reading options chains from a local dolt sql-server."""

import time
from dataclasses import dataclass
from datetime import date

import pymysql
import pymysql.cursors


@dataclass
class OptionsContract:
    symbol: str
    expiry_date: date
    contract_type: str  # "C" | "P"
    strike: float
    bid: float | None
    ask: float | None
    mid: float | None
    last: float | None
    volume: int | None
    open_interest: int | None
    iv: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None


class DoltOptionsClient:
    def __init__(self, url: str):
        # url: "mysql+pymysql://root@localhost:3307/options"
        # parse for pymysql
        rest = url.replace("mysql+pymysql://", "")
        user_host, db = rest.rsplit("/", 1)
        if "@" in user_host:
            user, host_port = user_host.rsplit("@", 1)
        else:
            user, host_port = "root", user_host
        if ":" in host_port:
            host, port = host_port.rsplit(":", 1)
            port = int(port)
        else:
            host, port = host_port, 3306
        self._connect_kwargs = dict(host=host, port=port, user=user, database=db,
                                     cursorclass=pymysql.cursors.DictCursor)

    def _connect(self):
        return pymysql.connect(**self._connect_kwargs)

    def ping(self) -> bool:
        try:
            conn = self._connect()
            conn.close()
            return True
        except Exception:
            return False

    def fetch_chain(
        self, symbol: str, as_of: date, retries: int = 3
    ) -> list[OptionsContract]:
        sql = """
            SELECT underlying, expiration, type, strike,
                   bid, ask, (bid+ask)/2 as mid, last,
                   volume, open_interest,
                   implied_volatility as iv,
                   delta, gamma, theta, vega
            FROM options
            WHERE underlying = %s AND date = %s
        """
        for attempt in range(retries):
            try:
                conn = self._connect()
                with conn.cursor() as cur:
                    cur.execute(sql, (symbol.upper(), as_of.isoformat()))
                    rows = cur.fetchall()
                conn.close()
                return [self._row_to_contract(r) for r in rows]
            except Exception as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)

    def _row_to_contract(self, row: dict) -> OptionsContract:
        return OptionsContract(
            symbol=row["underlying"],
            expiry_date=row["expiration"] if isinstance(row["expiration"], date)
                        else date.fromisoformat(str(row["expiration"])),
            contract_type=row["type"],
            strike=float(row["strike"]),
            bid=float(row["bid"]) if row["bid"] is not None else None,
            ask=float(row["ask"]) if row["ask"] is not None else None,
            mid=float(row["mid"]) if row["mid"] is not None else None,
            last=float(row["last"]) if row["last"] is not None else None,
            volume=int(row["volume"]) if row["volume"] is not None else None,
            open_interest=int(row["open_interest"]) if row["open_interest"] is not None else None,
            iv=float(row["iv"]) if row["iv"] is not None else None,
            delta=float(row["delta"]) if row["delta"] is not None else None,
            gamma=float(row["gamma"]) if row["gamma"] is not None else None,
            theta=float(row["theta"]) if row["theta"] is not None else None,
            vega=float(row["vega"]) if row["vega"] is not None else None,
        )
```

- [ ] **Step 6: Commit**
```bash
git add src/options_agent/data/ tests/options_agent/unit/test_expiries.py
git commit -m "feat(options-agent): slice 2 - dolt client and expiry computation"
```

---

## Task 8: Slice 2 — Chain ingestion, DB model, migration

**Files:**
- Modify: `src/db/models.py` — add OptionsEodChain
- Create: `src/db/migrations/versions/20260419_0002_add_options_eod_chains.py`
- Create: `src/options_agent/data/chain_ingester.py`
- Create: `tests/options_agent/integration/test_dolt_ingest.py`

- [ ] **Step 1: Add OptionsEodChain to src/db/models.py**

```python
class OptionsEodChain(Base):
    """EOD options chain data ingested from Dolthub."""

    __tablename__ = "options_eod_chains"

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(16), ForeignKey("stocks.symbol"), nullable=False)
    as_of_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    expiry_bucket = Column(String(16), nullable=False)  # current_week/next_week/monthly
    contract_type = Column(String(1), nullable=False)   # C or P
    strike = Column(NUMERIC(10, 2), nullable=False)
    bid = Column(NUMERIC(10, 4))
    ask = Column(NUMERIC(10, 4))
    mid = Column(NUMERIC(10, 4))
    last = Column(NUMERIC(10, 4))
    volume = Column(Integer)
    open_interest = Column(Integer)
    iv = Column(NUMERIC(8, 4))
    delta = Column(NUMERIC(8, 4))
    gamma = Column(NUMERIC(10, 6))
    theta = Column(NUMERIC(10, 6))
    vega = Column(NUMERIC(10, 6))
    ingested_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "symbol", "as_of_date", "expiry_date", "contract_type", "strike",
            name="uq_chain_contract",
        ),
        Index("ix_chain_symbol_asof", "symbol", "as_of_date"),
        Index("ix_chain_expiry_bucket", "symbol", "as_of_date", "expiry_bucket"),
    )
```

- [ ] **Step 2: Generate and apply migration**
```bash
alembic revision --autogenerate -m "add_options_eod_chains"
# rename to 20260419_0002_add_options_eod_chains.py
alembic upgrade head
```

- [ ] **Step 3: Write integration test with mock dolt**

`tests/options_agent/integration/test_dolt_ingest.py`:
```python
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _mock_contracts(symbol: str, expiry: date) -> list:
    from src.options_agent.data.dolt_client import OptionsContract
    return [
        OptionsContract(
            symbol=symbol, expiry_date=expiry, contract_type="C",
            strike=185.0, bid=2.5, ask=2.7, mid=2.6, last=2.55,
            volume=1500, open_interest=3000, iv=0.28,
            delta=0.52, gamma=0.045, theta=-0.08, vega=0.15,
        ),
        OptionsContract(
            symbol=symbol, expiry_date=expiry, contract_type="P",
            strike=180.0, bid=1.8, ask=2.0, mid=1.9, last=1.85,
            volume=800, open_interest=2000, iv=0.31,
            delta=-0.45, gamma=0.040, theta=-0.07, vega=0.12,
        ),
    ]


def test_ingest_persists_contracts(db_session):
    from src.options_agent.data.chain_ingester import ChainIngester
    from src.db.models import OptionsEodChain
    from src.options_agent.data.expiries import ExpiryBucket

    mock_client = MagicMock()
    as_of = date(2026, 4, 18)
    expiry = date(2026, 4, 24)
    mock_client.fetch_chain.return_value = _mock_contracts("AAPL", expiry)

    ingester = ChainIngester(dolt_client=mock_client, session=db_session)
    bucket = ExpiryBucket(label="current_week", expiry=expiry)
    count = ingester.ingest_for_symbol("AAPL", as_of=as_of, buckets=[bucket])

    assert count == 2
    rows = db_session.query(OptionsEodChain).filter_by(symbol="AAPL").all()
    assert len(rows) == 2


def test_ingest_idempotent(db_session):
    from src.options_agent.data.chain_ingester import ChainIngester
    from src.db.models import OptionsEodChain
    from src.options_agent.data.expiries import ExpiryBucket

    mock_client = MagicMock()
    as_of = date(2026, 4, 18)
    expiry = date(2026, 4, 24)
    mock_client.fetch_chain.return_value = _mock_contracts("AAPL", expiry)
    bucket = ExpiryBucket(label="current_week", expiry=expiry)
    ingester = ChainIngester(dolt_client=mock_client, session=db_session)

    ingester.ingest_for_symbol("AAPL", as_of=as_of, buckets=[bucket])
    ingester.ingest_for_symbol("AAPL", as_of=as_of, buckets=[bucket])

    count = db_session.query(OptionsEodChain).filter_by(symbol="AAPL").count()
    assert count == 2  # no duplicates
```

- [ ] **Step 4: Run — confirm fail**
```bash
pytest tests/options_agent/integration/test_dolt_ingest.py -v
```
Expected: ImportError on ChainIngester

- [ ] **Step 5: Implement chain_ingester.py**

`src/options_agent/data/chain_ingester.py`:
```python
"""Orchestrates pulling options chains from Dolthub into PostgreSQL."""

from datetime import date, datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.db.models import OptionsEodChain
from src.options_agent.data.dolt_client import DoltOptionsClient
from src.options_agent.data.expiries import ExpiryBucket


class ChainIngester:
    def __init__(self, dolt_client: DoltOptionsClient, session: Session):
        self._client = dolt_client
        self._session = session

    def ingest_for_symbol(
        self,
        symbol: str,
        as_of: date,
        buckets: list[ExpiryBucket],
    ) -> int:
        total = 0
        now = datetime.now(timezone.utc)
        for bucket in buckets:
            contracts = self._client.fetch_chain(symbol, as_of)
            relevant = [c for c in contracts if c.expiry_date == bucket.expiry]
            if not relevant:
                continue
            rows = [
                {
                    "symbol": c.symbol,
                    "as_of_date": as_of,
                    "expiry_date": c.expiry_date,
                    "expiry_bucket": bucket.label,
                    "contract_type": c.contract_type,
                    "strike": c.strike,
                    "bid": c.bid,
                    "ask": c.ask,
                    "mid": c.mid,
                    "last": c.last,
                    "volume": c.volume,
                    "open_interest": c.open_interest,
                    "iv": c.iv,
                    "delta": c.delta,
                    "gamma": c.gamma,
                    "theta": c.theta,
                    "vega": c.vega,
                    "ingested_at": now,
                }
                for c in relevant
            ]
            stmt = pg_insert(OptionsEodChain).values(rows).on_conflict_do_nothing(
                constraint="uq_chain_contract"
            )
            result = self._session.execute(stmt)
            self._session.commit()
            total += result.rowcount
        return total

    def ingest_for_symbols(
        self,
        symbols: list[str],
        as_of: date,
        buckets: list[ExpiryBucket],
    ) -> int:
        return sum(self.ingest_for_symbol(s, as_of, buckets) for s in symbols)
```

- [ ] **Step 6: Run — confirm pass**
```bash
pytest tests/options_agent/integration/test_dolt_ingest.py -v
```

- [ ] **Step 7: Add nightly job to scheduler**

In `src/data_fetcher/scheduler.py`, inside `_add_jobs` (or equivalent method):
```python
from src.options_agent.data.expiries import determine_target_expiries
from src.options_agent.data.chain_ingester import ChainIngester
from src.options_agent.data.dolt_client import DoltOptionsClient
from src.options_agent.config import get_options_config
import subprocess

def _run_options_nightly(session):
    cfg = get_options_config()
    # 1. Pull latest data
    subprocess.run(
        ["dolt", "pull"], cwd=cfg.dolt_repo_path, timeout=300, check=False
    )
    # 2. Ingest chains for all watchlist symbols
    from src.db.models import WatchlistSymbol
    symbols = [row.symbol for row in session.query(WatchlistSymbol.symbol).distinct()]
    buckets = determine_target_expiries(from src.datetime import date; date.today())
    client = DoltOptionsClient(cfg.dolt_options_url)
    ingester = ChainIngester(dolt_client=client, session=session)
    ingester.ingest_for_symbols(symbols, date.today(), buckets)
```

Note: wire this into APScheduler at 03:00 ET in the existing scheduler setup code (follow the existing `add_job` pattern in `scheduler.py`).

- [ ] **Step 8: Run make ci**
```bash
make ci
```

- [ ] **Step 9: Commit**
```bash
git add src/options_agent/data/ src/db/models.py src/db/migrations/ src/data_fetcher/scheduler.py tests/options_agent/integration/
git commit -m "feat(options-agent): slice 2 - Dolthub ingestion and nightly job"
```

**SLICE 2 CHECKPOINT** — human sign-off required.

---

## Task 9: Slice 3 — Real IV IVR upgrade

**Files:**
- Modify: `src/options_agent/ivr.py` — add `compute_ivr_from_implied` and `compute_atm_iv`
- Create: `tests/options_agent/unit/test_ivr_implied.py`

- [ ] **Step 1: Write tests**

`tests/options_agent/unit/test_ivr_implied.py`:
```python
from datetime import date


def _make_chain_rows(spot: float, n_strikes: int = 10):
    from src.options_agent.data.dolt_client import OptionsContract
    strikes = [spot - 10 + i * 2 for i in range(n_strikes)]
    rows = []
    for k in strikes:
        rows.append(OptionsContract(
            symbol="AAPL", expiry_date=date(2026, 4, 24), contract_type="C",
            strike=k, bid=None, ask=None, mid=None, last=None,
            volume=None, open_interest=None, iv=0.25 + abs(k - spot) * 0.002,
            delta=None, gamma=None, theta=None, vega=None,
        ))
        rows.append(OptionsContract(
            symbol="AAPL", expiry_date=date(2026, 4, 24), contract_type="P",
            strike=k, bid=None, ask=None, mid=None, last=None,
            volume=None, open_interest=None, iv=0.27 + abs(k - spot) * 0.002,
            delta=None, gamma=None, theta=None, vega=None,
        ))
    return rows


def test_compute_atm_iv_returns_average_of_call_and_put():
    from src.options_agent.ivr import compute_atm_iv
    chain = _make_chain_rows(spot=185.0)
    atm_iv = compute_atm_iv(chain, spot=185.0)
    assert 0.15 <= atm_iv <= 1.5


def test_ivr_from_implied_calculation_basis(db_session):
    from src.options_agent.ivr import compute_ivr_from_implied
    from src.db.models import IVRSnapshot
    from datetime import datetime, timezone
    # Seed 252 days of historical ATM IV
    for i in range(252):
        db_session.add(IVRSnapshot(
            symbol="AAPL",
            as_of_date=date(2025, 1, 1),
            ivr=float(i % 100),
            current_hv=0.20 + i * 0.001,
            calculation_basis="hv_proxy",
            computed_at=datetime.now(timezone.utc),
        ))
    db_session.commit()
    chain = _make_chain_rows(spot=185.0)
    result = compute_ivr_from_implied(
        session=db_session, symbol="AAPL", chain=chain, spot=185.0, as_of=date(2026, 4, 18)
    )
    assert result.calculation_basis == "implied"
    assert 0 <= result.ivr <= 100


def test_ivr_implied_falls_back_to_hv_proxy_with_insufficient_history(db_session):
    from tests.options_agent.conftest import synthetic_bars_rising_volatility
    from src.options_agent.ivr import compute_ivr_from_implied
    chain = _make_chain_rows(spot=185.0)
    result = compute_ivr_from_implied(
        session=db_session, symbol="AAPL", chain=chain, spot=185.0,
        as_of=date(2026, 4, 18), bars=synthetic_bars_rising_volatility()
    )
    assert result.calculation_basis == "hv_proxy"
```

- [ ] **Step 2: Run — confirm fail**
```bash
pytest tests/options_agent/unit/test_ivr_implied.py -v
```

- [ ] **Step 3: Implement compute_atm_iv and compute_ivr_from_implied**

Append to `src/options_agent/ivr.py`:
```python
def compute_atm_iv(chain: list, spot: float) -> float:
    """Average IV of ATM call and ATM put (nearest strike to spot)."""
    calls = [c for c in chain if c.contract_type == "C" and c.iv is not None]
    puts = [c for c in chain if c.contract_type == "P" and c.iv is not None]
    if not calls or not puts:
        raise ValueError("No contracts with IV data")
    atm_call = min(calls, key=lambda c: abs(c.strike - spot))
    atm_put = min(puts, key=lambda c: abs(c.strike - spot))
    return (atm_call.iv + atm_put.iv) / 2


def compute_ivr_from_implied(
    session,
    symbol: str,
    chain: list,
    spot: float,
    as_of: date,
    lookback: int = 252,
    bars: "pd.DataFrame | None" = None,
) -> IVRResult:
    """IVR from real implied volatility; falls back to HV proxy if history insufficient."""
    from src.db.models import IVRSnapshot

    historical = (
        session.query(IVRSnapshot.current_hv)
        .filter_by(symbol=symbol, calculation_basis="implied")
        .order_by(IVRSnapshot.as_of_date.asc())
        .limit(lookback)
        .all()
    )
    if len(historical) < lookback:
        if bars is None:
            raise InsufficientHistoryError(
                f"Only {len(historical)} days of implied IV history; need {lookback}"
            )
        return compute_ivr_from_hv(bars)

    current_iv = compute_atm_iv(chain, spot)
    history = np.array([float(r[0]) for r in historical])
    hv_min = float(history.min())
    hv_max = float(history.max())
    ivr = 0.0 if hv_max == hv_min else (current_iv - hv_min) / (hv_max - hv_min) * 100

    return IVRResult(
        ivr=round(ivr, 2),
        current_hv=round(current_iv, 4),
        hv_min=round(hv_min, 4),
        hv_max=round(hv_max, 4),
        calculation_basis="implied",
        as_of=as_of,
    )
```

- [ ] **Step 4: Run — confirm pass**
```bash
pytest tests/options_agent/unit/test_ivr_implied.py -v
```

- [ ] **Step 5: Run make ci**
```bash
make ci
```

- [ ] **Step 6: Commit**
```bash
git add src/options_agent/ivr.py tests/options_agent/unit/test_ivr_implied.py
git commit -m "feat(options-agent): slice 3 - real implied IV IVR upgrade"
```

**SLICE 3 CHECKPOINT** — human sign-off required.

---

## Task 10: Slice 4 — Regime detector model and migration

**Files:**
- Modify: `src/db/models.py` — add RegimeSnapshot
- Create migration file

- [ ] **Step 1: Add RegimeSnapshot to models**

```python
class RegimeSnapshot(Base):
    """Market regime classification per symbol per date."""

    __tablename__ = "regime_snapshots"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(16), nullable=False)
    as_of_date = Column(DateTime, nullable=False)
    regime = Column(String(16), nullable=False)     # trending|ranging|transitional
    direction = Column(String(16))                   # bullish|bearish|neutral|unclear
    adx = Column(NUMERIC(6, 2))
    atr_pct = Column(NUMERIC(6, 4))
    spy_trend_20d = Column(NUMERIC(8, 6))
    computed_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "as_of_date", name="uq_regime_symbol_date"),
        Index("ix_regime_symbol", "symbol"),
    )
```

- [ ] **Step 2: Generate and apply migration**
```bash
alembic revision --autogenerate -m "add_regime_snapshots"
# rename to 20260419_0003_add_regime_snapshots.py
alembic upgrade head
```

- [ ] **Step 3: Commit**
```bash
git add src/db/models.py src/db/migrations/
git commit -m "feat(options-agent): add RegimeSnapshot model and migration"
```

---

## Task 11: Slice 4 — Regime detector implementation

**Files:**
- Create: `src/options_agent/signals/regime.py`
- Create: `tests/options_agent/unit/test_regime_detector.py`
- Create: `tests/options_agent/fixtures/bars/*.csv` (via fixture helpers)

- [ ] **Step 1: Write regime detector tests**

`tests/options_agent/unit/test_regime_detector.py`:
```python
import numpy as np
import pandas as pd
import pytest
from datetime import date, timedelta


def _trending_bars(n=120, slope=0.005) -> pd.DataFrame:
    """Strong uptrend — ADX will be high."""
    np.random.seed(1)
    closes = np.cumprod(1 + np.random.normal(slope, 0.008, n)) * 100
    high = closes * 1.005
    low = closes * 0.995
    return pd.DataFrame({"open": closes*0.999, "high": high, "low": low, "close": closes,
                          "volume": [1_000_000]*n})


def _ranging_bars(n=120) -> pd.DataFrame:
    """Tight range — ADX low, ATR% small."""
    np.random.seed(2)
    closes = 100 + np.random.normal(0, 0.3, n)
    high = closes + 0.2
    low = closes - 0.2
    return pd.DataFrame({"open": closes, "high": high, "low": low, "close": closes,
                          "volume": [500_000]*n})


def _spy_trending_up(n=120) -> pd.DataFrame:
    np.random.seed(3)
    closes = np.cumprod(1 + np.random.normal(0.003, 0.006, n)) * 500
    return pd.DataFrame({"close": closes, "high": closes*1.003, "low": closes*0.997,
                          "open": closes, "volume": [50_000_000]*n})


def _spy_flat(n=120) -> pd.DataFrame:
    return pd.DataFrame({"close": [500.0]*n, "high": [501.0]*n, "low": [499.0]*n,
                          "open": [500.0]*n, "volume": [50_000_000]*n})


def test_trending_bullish():
    from src.options_agent.signals.regime import detect_regime
    result = detect_regime(_trending_bars(), _spy_trending_up())
    assert result.regime == "trending"
    assert result.direction == "bullish"
    assert result.adx > 25


def test_ranging():
    from src.options_agent.signals.regime import detect_regime
    result = detect_regime(_ranging_bars(), _spy_flat())
    assert result.regime == "ranging"
    assert result.adx < 20


def test_result_dataclass_fields():
    from src.options_agent.signals.regime import detect_regime, RegimeResult
    result = detect_regime(_trending_bars(), _spy_trending_up())
    assert isinstance(result, RegimeResult)
    assert result.regime in ("trending", "ranging", "transitional")
    assert isinstance(result.adx, float)
    assert isinstance(result.atr_pct, float)
```

- [ ] **Step 2: Run — confirm fail**
```bash
pytest tests/options_agent/unit/test_regime_detector.py -v
```

- [ ] **Step 3: Implement regime detector**

`src/options_agent/signals/regime.py`:
```python
"""Market regime detection: trending / ranging / transitional."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


@dataclass
class RegimeResult:
    regime: Literal["trending", "ranging", "transitional"]
    direction: Literal["bullish", "bearish", "neutral", "unclear"] | None
    adx: float
    atr_pct: float
    spy_trend_20d: float


def _adx(df: pd.DataFrame, period: int = 14) -> float:
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    tr = np.maximum(high[1:] - low[1:],
         np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    dm_plus = np.where((high[1:] - high[:-1]) > (low[:-1] - low[1:]),
                       np.maximum(high[1:] - high[:-1], 0), 0)
    dm_minus = np.where((low[:-1] - low[1:]) > (high[1:] - high[:-1]),
                        np.maximum(low[:-1] - low[1:], 0), 0)

    def ema(x):
        result = np.zeros_like(x)
        result[period-1] = x[:period].mean()
        k = 1 / period
        for i in range(period, len(x)):
            result[i] = x[i] * k + result[i-1] * (1 - k)
        return result

    atr_s = ema(tr)
    di_plus = 100 * ema(dm_plus) / np.where(atr_s == 0, 1, atr_s)
    di_minus = 100 * ema(dm_minus) / np.where(atr_s == 0, 1, atr_s)
    dx = 100 * abs(di_plus - di_minus) / np.where(di_plus + di_minus == 0, 1, di_plus + di_minus)
    adx_val = ema(dx)
    return float(adx_val[-1])


def _atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    tr = np.maximum(high[1:] - low[1:],
         np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    atr = tr[-period:].mean()
    return float(atr / close[-1])


def _spy_trend_slope(spy: pd.DataFrame, window: int = 20) -> float:
    closes = spy["close"].values[-window:]
    x = np.arange(window)
    slope = np.polyfit(x, closes, 1)[0]
    return float(slope / closes[0])


def detect_regime(bars: pd.DataFrame, spy_bars: pd.DataFrame) -> RegimeResult:
    adx = _adx(bars)
    atr_pct = _atr_pct(bars)
    spy_trend = _spy_trend_slope(spy_bars)

    if adx < 20 and atr_pct < 0.015:
        return RegimeResult(regime="ranging", direction="neutral",
                            adx=adx, atr_pct=atr_pct, spy_trend_20d=spy_trend)

    if adx > 25 and atr_pct <= 0.03:
        if spy_trend > 0.001:
            direction = "bullish"
        elif spy_trend < -0.001:
            direction = "bearish"
        else:
            ema20 = bars["close"].ewm(span=20).mean().iloc[-1]
            direction = "bullish" if bars["close"].iloc[-1] > ema20 else "bearish"
        return RegimeResult(regime="trending", direction=direction,
                            adx=adx, atr_pct=atr_pct, spy_trend_20d=spy_trend)

    return RegimeResult(regime="transitional", direction="unclear",
                        adx=adx, atr_pct=atr_pct, spy_trend_20d=spy_trend)
```

- [ ] **Step 4: Run — confirm pass**
```bash
pytest tests/options_agent/unit/test_regime_detector.py -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Add regime API endpoint**

Add to `src/api/options/schemas.py`:
```python
class RegimeResponse(BaseModel):
    symbol: str
    regime: str
    direction: str | None
    adx: float
    atr_pct: float
    as_of_date: date
```

Add to `src/api/options/routes.py`:
```python
from src.api.options.schemas import RegimeResponse
from src.db.models import RegimeSnapshot

@router.get("/regime/{symbol}", response_model=RegimeResponse)
def get_regime(symbol: str, db: Session = Depends(get_db)):
    snap = (
        db.query(RegimeSnapshot)
        .filter_by(symbol=symbol.upper())
        .order_by(RegimeSnapshot.as_of_date.desc())
        .first()
    )
    if not snap:
        raise HTTPException(status_code=404, detail=f"No regime data for {symbol}")
    return RegimeResponse(
        symbol=symbol.upper(),
        regime=snap.regime,
        direction=snap.direction,
        adx=float(snap.adx or 0),
        atr_pct=float(snap.atr_pct or 0),
        as_of_date=snap.as_of_date,
    )
```

- [ ] **Step 6: Add regime pill to frontend symbol-row.tsx**

In `frontend/src/lib/options-api.ts`, add:
```typescript
export interface RegimeData {
  symbol: string;
  regime: "trending" | "ranging" | "transitional";
  direction: string | null;
  adx: number;
  atr_pct: number;
  as_of_date: string;
}
// in optionsAPI:
  getRegime: (symbol: string): Promise<RegimeData> =>
    apiFetch(`/api/options/regime/${symbol}`),
```

In `symbol-row.tsx`, add regime resource and pill:
```tsx
const [regime] = createResource<RegimeData | null>(
  () => props.symbol,
  async (sym) => { try { return await optionsAPI.getRegime(sym); } catch { return null; } }
);

function regimePill(r: RegimeData) {
  const label = r.regime === "trending"
    ? (r.direction === "bullish" ? "Trending ↑" : "Trending ↓")
    : r.regime === "ranging" ? "Ranging" : "Transitional";
  const cls = r.regime === "trending" && r.direction === "bullish"
    ? "bg-green-100 text-green-800"
    : r.regime === "trending" ? "bg-red-100 text-red-800"
    : r.regime === "ranging" ? "bg-gray-100 text-gray-700"
    : "bg-amber-100 text-amber-800";
  return <span class={`text-xs font-medium px-1.5 py-0.5 rounded ${cls}`}>{label}</span>;
}

// In JSX:
<Show when={regime()}>
  {(r) => <td class="px-2 py-1">{regimePill(r())}</td>}
</Show>
```

- [ ] **Step 7: Run make ci**
```bash
make ci
```

- [ ] **Step 8: Commit**
```bash
git add src/options_agent/signals/regime.py src/api/options/ src/db/ frontend/src/
git commit -m "feat(options-agent): slice 4 - market regime detector and UI pill"
```

**SLICE 4 CHECKPOINT** — `make ci` green, watchlist shows IVR badges and regime pills. Human sign-off required before continuing to slices 5–9.

---

## Self-Review

**Spec coverage check:**
- [x] Slice 0: module scaffold, CI passes
- [x] Slice 1: IVR HV proxy, persistence, API `/api/options/ivr`, watchlist badge
- [x] Slice 2: Dolthub client, expiry computation, chain ingestion, nightly job, idempotency
- [x] Slice 3: real implied IV IVR, fallback to HV proxy, same API interface
- [x] Slice 4: regime detector (trending/ranging/transitional), API `/api/options/regime`, UI pill

**Placeholders:** None — all steps contain executable code.

**Type consistency:**
- `IVRResult` used in `compute_ivr_from_hv`, `compute_and_store_ivr`, `compute_ivr_from_implied` — consistent
- `RegimeResult` returned by `detect_regime`, consumed in route — consistent
- `OptionsContract` dataclass used in `DoltOptionsClient`, `ChainIngester`, `compute_atm_iv` — consistent
- `ExpiryBucket` used in `determine_target_expiries`, `ChainIngester` — consistent

---

**Continue with:** `docs/superpowers/plans/2026-04-19-options-agent-slices-5-9.md`
