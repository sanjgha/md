---
title: Market Data Infrastructure Design
description: Hybrid local storage + realtime monitoring system for 500 stock universe with EOD and intraday scanning
date: 2026-04-05
---

# Market Data Infrastructure Design

## Executive Summary

Build a hybrid market data infrastructure using MarketData.app (Starter tier, 10,000 credits/day) to support:
- **Phase 1:** EOD scanner on 500-stock universe → realtime monitoring of matched tickers → historical backtesting
- **Phase 2:** Options data, multi-provider support, dashboard integration, database indicator caching

**Architecture:** Modular Python application with PostgreSQL backend, pluggable DataProvider adapters, indicator caching framework, and flexible output abstraction. Clean separation enables scanner isolation, reduces code duplication, and supports future dashboard integration without rearchitecture.

---

## 1. Database Schema

PostgreSQL with 8 core tables optimized for time-series queries and market data patterns.

### 1.1 Reference Tables

```sql
-- Stock universe reference
CREATE TABLE stocks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255),
    sector VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 1.2 Price Data Tables

```sql
-- Daily OHLCV (1-year retention, bulk of storage)
CREATE TABLE daily_candles (
    id BIGSERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    open NUMERIC(10,2) NOT NULL,
    high NUMERIC(10,2) NOT NULL,
    low NUMERIC(10,2) NOT NULL,
    close NUMERIC(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_id, timestamp),
    INDEX (stock_id, timestamp DESC)  -- BRIN for time-series
);

-- Intraday bars (5m, 15m, 1h; 7-day retention)
CREATE TABLE intraday_candles (
    id BIGSERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    resolution VARCHAR(10) NOT NULL,  -- '5m', '15m', '1h'
    timestamp TIMESTAMP NOT NULL,
    open NUMERIC(10,2) NOT NULL,
    high NUMERIC(10,2) NOT NULL,
    low NUMERIC(10,2) NOT NULL,
    close NUMERIC(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_id, resolution, timestamp),
    INDEX (stock_id, timestamp DESC)
);

-- Realtime quotes with intraday summary (7-day retention)
-- Every quote from /v1/stocks/quotes/{symbol} includes day's open/high/low + 52-week levels
CREATE TABLE realtime_quotes (
    id BIGSERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    -- Level 1 quotes
    bid NUMERIC(10,2),
    ask NUMERIC(10,2),
    bid_size BIGINT,
    ask_size BIGINT,
    last NUMERIC(10,2),
    -- Today's intraday summary (provided by MarketData.app every quote)
    open NUMERIC(10,2),              -- today's open
    high NUMERIC(10,2),              -- today's high
    low NUMERIC(10,2),               -- today's low
    close NUMERIC(10,2),             -- previous day's close
    volume BIGINT,                   -- current day volume
    -- Price changes (from previous close)
    change NUMERIC(10,4),            -- absolute change
    change_pct NUMERIC(10,4),        -- percentage change
    -- 52-week reference levels
    week_52_high NUMERIC(10,2),
    week_52_low NUMERIC(10,2),
    -- Status
    status VARCHAR(50),              -- 'active', etc.
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX (stock_id, timestamp DESC)
);
```

**Design Note:** Realtime quotes capture bonus intraday data at zero cost:
- Today's OHLC enables intraday breakout scanning (e.g., price above today's high)
- 52-week levels enable swing/breakout detection
- Change % enables momentum filters
- Volume enables liquidity checks

### 1.3 Fundamental Data Tables

```sql
-- Earnings calendar (no retention limit; reference data)
CREATE TABLE earnings_calendar (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,
    earnings_date DATE NOT NULL,
    report_date TIMESTAMP,
    report_time VARCHAR(50),  -- 'before market open', 'after market close', 'during hours'
    currency VARCHAR(10),
    reported_eps NUMERIC(10,4),
    estimated_eps NUMERIC(10,4),
    -- Note: surpriseEPS = reported_eps - estimated_eps, calculate on read
    -- Note: surprise_pct = (surprise / estimated_eps) * 100, calculate on read
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_id, earnings_date),
    INDEX (earnings_date DESC)
);

-- Economic indicators (no retention limit)
CREATE TABLE economic_indicators (
    id SERIAL PRIMARY KEY,
    indicator_name VARCHAR(255) NOT NULL,
    release_date DATE NOT NULL,
    value NUMERIC(15,4),
    unit VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(indicator_name, release_date)
);
```

### 1.4 News & Options Tables

```sql
-- Stock news articles (no retention limit; audit trail)
CREATE TABLE stock_news (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    headline TEXT NOT NULL,
    content TEXT,
    source VARCHAR(255),      -- source domain
    publication_date TIMESTAMP NOT NULL,
    fetched_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX (stock_id, publication_date DESC),
    INDEX (publication_date DESC)
);

-- Options quotes with Greeks (Phase 2; 7-day retention initially)
CREATE TABLE options_quotes (
    id BIGSERIAL PRIMARY KEY,
    option_symbol VARCHAR(50) NOT NULL,  -- OCC format
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    bid NUMERIC(10,2),
    ask NUMERIC(10,2),
    bid_size BIGINT,
    ask_size BIGINT,
    last NUMERIC(10,2),
    volume BIGINT,
    open_interest BIGINT,
    -- Greeks (from MarketData.app)
    delta NUMERIC(10,4),
    gamma NUMERIC(10,4),
    theta NUMERIC(10,4),
    vega NUMERIC(10,4),
    iv NUMERIC(10,4),         -- implied volatility
    -- Underlying reference
    underlying_price NUMERIC(10,2),
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(option_symbol, timestamp),
    INDEX (stock_id, timestamp DESC)
);
```

### 1.5 Scanner & Monitoring Tables

```sql
-- Scanner results (persistent audit trail; no retention limit)
CREATE TABLE scanner_results (
    id BIGSERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    scanner_name VARCHAR(255) NOT NULL,
    result_metadata JSONB,    -- flexible schema for different scanners
    matched_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX (scanner_name, matched_at DESC),
    INDEX (stock_id, matched_at DESC)
);
```

---

## 2. Module Structure

```
md/
├── src/
│   ├── __init__.py
│   ├── config.py                 # Config, env vars, secrets management
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py             # SQLAlchemy ORM definitions
│   │   ├── connection.py         # DB connection pooling (5-20 conns)
│   │   └── migrations/           # Alembic schema versioning
│   ├── data_provider/
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract DataProvider interface
│   │   ├── marketdata_app.py     # MarketData.app implementation
│   │   └── exceptions.py         # Provider-specific errors
│   ├── data_fetcher/
│   │   ├── __init__.py
│   │   ├── fetcher.py            # Orchestrates all syncing
│   │   ├── scheduler.py          # APScheduler for daily runs
│   │   └── sync_service.py       # Realtime quote polling
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── indicators/
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Abstract Indicator interface
│   │   │   ├── cache.py          # In-memory caching during EOD run
│   │   │   ├── technical/
│   │   │   │   ├── moving_averages.py   # SMA, EMA, WMA
│   │   │   │   ├── momentum.py          # RSI, MACD, Stochastic
│   │   │   │   ├── volatility.py        # Bollinger Bands, ATR
│   │   │   │   └── volume.py            # OBV, On-Balance Volume
│   │   │   └── patterns/
│   │   │       ├── support_resistance.py # S/R levels, pivots
│   │   │       ├── breakouts.py         # Breakout pattern detection
│   │   │       └── candlestick.py       # Candlestick patterns
│   │   ├── base.py               # Abstract Scanner interface
│   │   ├── scanners/
│   │   │   ├── price_action.py   # Uses: S/R, breakouts, patterns
│   │   │   ├── momentum_scan.py  # Uses: RSI, MACD, momentum
│   │   │   └── volume_scan.py    # Uses: OBV, volume profile
│   │   ├── executor.py           # Runs scanners, manages cache
│   │   ├── registry.py           # Discovers/loads scanners
│   │   └── context.py            # ScanContext passed to scanners
│   ├── realtime_monitor/
│   │   ├── __init__.py
│   │   ├── monitor.py            # Tracks matched tickers, polls quotes
│   │   ├── alert_engine.py       # Evaluates alert rules
│   │   └── rules.py              # Predefined alert rules
│   ├── output/
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract OutputHandler interface
│   │   ├── cli.py                # CLI text output
│   │   ├── logger.py             # Persistent log files
│   │   ├── webhook.py            # Webhook for dashboard (Phase 2)
│   │   └── composite.py          # Send to multiple handlers
│   └── main.py                   # Entry point, CLI commands
├── tests/
│   ├── unit/
│   │   ├── test_indicators.py
│   │   ├── test_scanners.py
│   │   └── test_output_handlers.py
│   ├── integration/
│   │   ├── test_fetcher_db.py
│   │   └── test_end_to_end.py
│   └── fixtures/
│       └── mock_data.py
├── docs/
│   ├── superpowers/
│   │   └── specs/
│   └── architecture.md
├── pyproject.toml
├── Makefile
└── README.md
```

---

## 3. Data Provider Adapter Pattern

**Rationale:** Abstract MarketData.app API behind a standard interface to support provider swapping (Finnhub, YahooFinance, etc.) without rewriting fetcher logic.

### 3.1 Abstract Interface

```python
# src/data_provider/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

@dataclass
class Quote:
    timestamp: datetime
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: float
    # Intraday summary
    open: float              # today's open
    high: float              # today's high
    low: float               # today's low
    close: float             # previous close
    volume: int              # current day volume
    # Changes
    change: float            # absolute change from prev close
    change_pct: float        # percentage change
    # Reference levels
    week_52_high: float
    week_52_low: float
    status: str

@dataclass
class NewsArticle:
    symbol: str
    headline: str
    content: str
    source: str
    publication_date: datetime

@dataclass
class Earning:
    symbol: str
    fiscal_year: int
    fiscal_quarter: int
    earnings_date: datetime
    report_date: datetime
    report_time: str
    currency: str
    reported_eps: float
    estimated_eps: float

class DataProvider(ABC):
    """Abstract interface for market data providers."""

    @abstractmethod
    def get_daily_candles(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
    ) -> List[Candle]:
        """Fetch daily OHLCV."""
        pass

    @abstractmethod
    def get_intraday_candles(
        self,
        symbol: str,
        resolution: str,  # '5m', '15m', '1h'
        from_date: datetime,
        to_date: datetime,
    ) -> List[Candle]:
        """Fetch intraday bars."""
        pass

    @abstractmethod
    def get_realtime_quote(self, symbol: str) -> Quote:
        """Fetch current bid/ask/last with intraday summary."""
        pass

    @abstractmethod
    def get_earnings_history(
        self,
        symbol: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Earning]:
        """Fetch historical earnings."""
        pass

    @abstractmethod
    def get_news(
        self,
        symbol: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        countback: Optional[int] = None,
    ) -> List[NewsArticle]:
        """Fetch news articles."""
        pass
```

### 3.2 MarketData.app Implementation

```python
# src/data_provider/marketdata_app.py
import requests
from .base import DataProvider, Candle, Quote, NewsArticle, Earning

class MarketDataAppProvider(DataProvider):
    def __init__(self, api_token: str):
        self.base_url = "https://api.marketdata.app/v1"
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_token}"})

    def get_daily_candles(self, symbol: str, from_date: datetime, to_date: datetime) -> List[Candle]:
        """Fetch daily bars using cached feed for cost optimization."""
        url = f"{self.base_url}/stocks/candles/1d/{symbol}"
        params = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "feed": "cached",  # 1 credit per bulk request
        }
        resp = self.session.get(url, params=params)
        resp.raise_for_status()

        candles = []
        for result in resp.json()["results"]:
            candles.append(Candle(
                timestamp=datetime.fromisoformat(result["t"]),
                open=result["o"],
                high=result["h"],
                low=result["l"],
                close=result["c"],
                volume=result["v"]
            ))
        return candles

    def get_intraday_candles(
        self,
        symbol: str,
        resolution: str,
        from_date: datetime,
        to_date: datetime,
    ) -> List[Candle]:
        """Fetch intraday bars (5m, 15m, 1h)."""
        url = f"{self.base_url}/stocks/candles/{resolution}/{symbol}"
        params = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "feed": "cached",
        }
        resp = self.session.get(url, params=params)
        resp.raise_for_status()

        candles = []
        for result in resp.json()["results"]:
            candles.append(Candle(
                timestamp=datetime.fromisoformat(result["t"]),
                open=result["o"],
                high=result["h"],
                low=result["l"],
                close=result["c"],
                volume=result["v"]
            ))
        return candles

    def get_realtime_quote(self, symbol: str) -> Quote:
        """Fetch current quote with intraday summary."""
        url = f"{self.base_url}/stocks/quotes/{symbol}"
        params = {"feed": "live"}
        resp = self.session.get(url, params=params)
        resp.raise_for_status()

        data = resp.json()["results"][0]
        return Quote(
            timestamp=datetime.fromisoformat(data["updated"]),
            bid=data["bid"],
            ask=data["ask"],
            bid_size=data["bidSize"],
            ask_size=data["askSize"],
            last=data["last"],
            open=data["o"],
            high=data["h"],
            low=data["l"],
            close=data["c"],
            volume=data["volume"],
            change=data["change"],
            change_pct=data["changepct"],
            week_52_high=data["52weekHigh"],
            week_52_low=data["52weekLow"],
            status=data["status"]
        )

    def get_earnings_history(self, symbol: str, from_date=None, to_date=None) -> List[Earning]:
        """Fetch earnings history."""
        url = f"{self.base_url}/stocks/earnings/{symbol}"
        params = {}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()

        resp = self.session.get(url, params=params)
        resp.raise_for_status()

        earnings = []
        for result in resp.json()["results"]:
            earnings.append(Earning(
                symbol=symbol,
                fiscal_year=result["fiscalYear"],
                fiscal_quarter=result["fiscalQuarter"],
                earnings_date=datetime.fromisoformat(result["date"]),
                report_date=datetime.fromisoformat(result["reportDate"]),
                report_time=result["reportTime"],
                currency=result["currency"],
                reported_eps=result["reportedEPS"],
                estimated_eps=result["estimatedEPS"]
            ))
        return earnings

    def get_news(self, symbol: str, from_date=None, to_date=None, countback=None) -> List[NewsArticle]:
        """Fetch news articles."""
        url = f"{self.base_url}/stocks/news/{symbol}"
        params = {}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        if countback:
            params["countback"] = countback

        resp = self.session.get(url, params=params)
        resp.raise_for_status()

        data = resp.json()
        articles = []
        for i, headline in enumerate(data.get("headline", [])):
            articles.append(NewsArticle(
                symbol=data["symbol"][i] if isinstance(data["symbol"], list) else symbol,
                headline=headline,
                content=data["content"][i],
                source=data["source"][i],
                publication_date=datetime.fromisoformat(data["publicationDate"][i])
            ))
        return articles
```

**To swap providers:**
```python
# In configuration or DI
if config.DATA_PROVIDER == "marketdata":
    provider = MarketDataAppProvider(api_token)
elif config.DATA_PROVIDER == "finnhub":
    provider = FinnhubProvider(api_key)

fetcher = DataFetcher(provider)
```

---

## 4. Indicator Framework & Caching

**Rationale:** Scanners commonly use same indicators (SMA, RSI, etc.). Avoid recalculation by caching indicators within a single EOD run.

### 4.1 Shared Context

```python
# src/scanner/context.py
from dataclasses import dataclass
from typing import Dict, List
import numpy as np

@dataclass
class ScanContext:
    stock_id: int
    symbol: str
    daily_candles: List[Candle]
    intraday_candles: Dict[str, List[Candle]]  # {'5m': [...], '15m': [...]}
    indicator_cache: 'IndicatorCache'

    def get_indicator(self, name: str, **kwargs) -> np.ndarray:
        """Retrieve (or calculate once) an indicator."""
        return self.indicator_cache.get_or_compute(name, self.daily_candles, **kwargs)
```

### 4.2 Indicator Cache

```python
# src/scanner/indicators/cache.py
from typing import Dict, Tuple, Any
import numpy as np

class IndicatorCache:
    def __init__(self, indicators_registry: Dict[str, 'Indicator']):
        self.registry = indicators_registry
        self._cache = {}

    def get_or_compute(self, name: str, candles: List[Candle], **kwargs) -> np.ndarray:
        """Get indicator from cache or compute once."""
        cache_key = (name, tuple(sorted(kwargs.items())))

        if cache_key in self._cache:
            return self._cache[cache_key]

        indicator = self.registry[name]
        result = indicator.compute(candles, **kwargs)
        self._cache[cache_key] = result
        return result
```

### 4.3 Indicator Interface

```python
# src/scanner/indicators/base.py
from abc import ABC, abstractmethod
import numpy as np

class Indicator(ABC):
    @abstractmethod
    def compute(self, candles: List[Candle], **kwargs) -> np.ndarray:
        """Compute indicator, return numpy array."""
        pass

# Examples
class SMA(Indicator):
    def compute(self, candles: List[Candle], period: int = 50) -> np.ndarray:
        closes = np.array([c.close for c in candles])
        return np.convolve(closes, np.ones(period) / period, mode='valid')

class RSI(Indicator):
    def compute(self, candles: List[Candle], period: int = 14) -> np.ndarray:
        closes = np.array([c.close for c in candles])
        deltas = np.diff(closes)
        gains = np.maximum(deltas, 0)
        losses = np.abs(np.minimum(deltas, 0))
        # ... RSI calculation ...
        return rsi_values
```

### 4.4 Scanner Usage

```python
# src/scanner/scanners/price_action.py
class PriceActionScanner(Scanner):
    def scan(self, context: ScanContext) -> List[ScanResult]:
        # Indicators calculated once, cached across scanners
        sma50 = context.get_indicator('sma', period=50)
        sma200 = context.get_indicator('sma', period=200)
        support = context.get_indicator('support_levels')

        matches = []
        # Logic using cached indicators
        if context.daily_candles[-1].close > sma50[-1]:
            if context.daily_candles[-1].low <= support[-1]:
                matches.append(ScanResult(
                    stock_id=context.stock_id,
                    scanner_name='price_action',
                    metadata={'reason': 'price_action_support_bounce'}
                ))
        return matches
```

---

## 5. Realtime Monitor & Output Abstraction

### 5.1 Realtime Monitor

```python
# src/realtime_monitor/monitor.py
class RealtimeMonitor:
    def __init__(self, provider: DataProvider, db: Database, output_handler: OutputHandler):
        self.provider = provider
        self.db = db
        self.output_handler = output_handler
        self.watched_tickers = set()

    def load_scanner_results(self, scanner_name: str):
        """Load tickers matched by EOD scanner."""
        results = self.db.get_scanner_results(scanner_name, today)
        self.watched_tickers = {r.stock.symbol for r in results}

    def poll_quotes(self, interval_seconds: int = 5):
        """Poll realtime quotes for watched tickers during market hours."""
        while market_hours():
            for ticker in self.watched_tickers:
                try:
                    quote = self.provider.get_realtime_quote(ticker)
                    self.db.insert_quote(ticker, quote)

                    # Trigger alert rules
                    if self.alert_engine.should_alert(ticker, quote):
                        alert = Alert(ticker=ticker, quote=quote, reason="target_hit")
                        self.output_handler.emit_alert(alert)
                except Exception as e:
                    logger.error(f"Error fetching {ticker}: {e}")

            time.sleep(interval_seconds)
```

### 5.2 Output Handler Abstraction

```python
# src/output/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ScanResult:
    stock_id: int
    scanner_name: str
    metadata: dict

@dataclass
class Alert:
    ticker: str
    reason: str
    quote: 'Quote'
    timestamp: datetime = None

class OutputHandler(ABC):
    """Abstraction for alert/result destinations."""

    @abstractmethod
    def emit_scan_result(self, result: ScanResult):
        pass

    @abstractmethod
    def emit_alert(self, alert: Alert):
        pass
```

### 5.3 Implementations

```python
# src/output/cli.py
class CLIOutputHandler(OutputHandler):
    def emit_scan_result(self, result: ScanResult):
        print(f"[{result.scanner_name}] Stock {result.stock_id} matched: {result.metadata}")

    def emit_alert(self, alert: Alert):
        print(f"🚨 ALERT: {alert.ticker} {alert.reason} @ ${alert.quote.last}")

# src/output/logger.py
class LogFileOutputHandler(OutputHandler):
    def __init__(self, log_file: str = "logs/market_data.log"):
        self.logger = logging.getLogger("market_data")
        self.logger.addHandler(logging.FileHandler(log_file))

    def emit_scan_result(self, result: ScanResult):
        self.logger.info(f"SCAN: {result.scanner_name} {result.stock_id}")

    def emit_alert(self, alert: Alert):
        self.logger.warning(f"ALERT: {alert.ticker} {alert.reason}")

# src/output/composite.py
class CompositeOutputHandler(OutputHandler):
    """Send to multiple handlers simultaneously."""
    def __init__(self, handlers: List[OutputHandler]):
        self.handlers = handlers

    def emit_scan_result(self, result: ScanResult):
        for handler in self.handlers:
            handler.emit_scan_result(result)

    def emit_alert(self, alert: Alert):
        for handler in self.handlers:
            handler.emit_alert(alert)
```

**Usage:**
```python
# Send to CLI + logs simultaneously
output = CompositeOutputHandler([
    CLIOutputHandler(),
    LogFileOutputHandler(),
    # WebhookOutputHandler(dashboard_url) in Phase 2
])
```

---

## 6. Daily Execution Flow

### 6.1 EOD Pipeline (Post-market close ~4:15 PM ET)

```
1. DataFetcher.sync_daily()
   ├─ Fetch daily candles (500 stocks, 1 year history) → DB
   │  └─ Cost: ~500 credits (1 credit per bulk request)
   ├─ Fetch intraday bars (500 stocks, 5m/15m/1h, past 7 days) → DB
   │  └─ Cost: ~1500 credits (3 resolutions × 500 stocks)
   ├─ Fetch earnings calendar (500 stocks) → DB
   │  └─ Cost: ~500 credits
   ├─ Fetch news (500 stocks, last 50 articles each) → DB
   │  └─ Cost: ~500 credits
   └─ Cleanup: Delete intraday data older than 7 days

2. ScannerExecutor.run_eod()
   ├─ Load daily candles for 500 stocks into memory
   ├─ Initialize IndicatorCache (empty)
   ├─ For each scanner in registry:
   │  ├─ Create ScanContext(stock_id, candles, indicator_cache)
   │  ├─ Run scanner.scan(context) → returns List[ScanResult]
   │  └─ For each match:
   │     ├─ Insert into scanner_results table
   │     └─ output_handler.emit_scan_result()
   └─ Summary output to CLI + logs

3. RealtimeMonitor startup
   ├─ Load today's scanner results
   ├─ Build watched_tickers set (10-50 active stocks)
   └─ Begin polling quotes during market hours
```

**Daily credit usage:**
- Daily candles: 500
- Intraday candles: 1500
- Earnings: 500
- News: 500
- Total: ~3000 credits (well within 10,000 daily limit)

### 6.2 Data Retention Policy

| Data | Retention | Reason |
|------|-----------|--------|
| Daily candles | 1 year | Backtesting baseline |
| Intraday candles | 7 days | Realtime analysis, avoid DB bloat |
| Realtime quotes | 7 days | Recent tick history, reconstruction |
| Earnings calendar | Infinite | Reference data, no cost |
| Economic indicators | Infinite | Reference data, no cost |
| Stock news | Infinite | Audit trail, no cost |
| Scanner results | Infinite | Audit trail, no cost |

---

## 7. Error Handling & Resilience

### 7.1 Provider-Level (Data Fetch Failures)

- **Retry with exponential backoff:** 1s → 2s → 4s → 8s (max 5 retries)
- **Circuit breaker:** If provider fails 5 consecutive times, stop trying for 1 hour
- **Alert output:** Log failures for manual intervention

### 7.2 Database-Level (Write Failures)

- **Connection pooling:** Min 5, max 20 connections with automatic recovery
- **Retry on transient errors:** Deadlock, timeout (max 3 retries)
- **Persistent error log:** All failures logged with context for debugging

### 7.3 Scanner-Level (Indicator Calc Failures)

- **Isolation:** Individual scanner failure doesn't break pipeline
- **Logging:** Error logged with stock/scanner context
- **Graceful degradation:** Continue to next scanner, partial results acceptable

---

## 8. Testing Strategy

| Layer | Approach | Example |
|-------|----------|---------|
| **Unit** | Mock DB, provider; test logic | Does RSI scanner correctly identify oversold? |
| **Integration** | Real PostgreSQL (Docker), mock provider | Do scanner results insert correctly? |
| **E2E** | Real provider (staging account), real DB | Full EOD run: fetch → scan → output |
| **NFT** | 500-stock load test, credit/latency measurement | How fast does EOD complete? Do we exceed daily credits? |

**Test structure:**
```
tests/
├── unit/
│   ├── test_indicators.py       # SMA, RSI, support_levels
│   ├── test_scanners.py         # price_action, momentum, volume
│   └── test_output_handlers.py
├── integration/
│   ├── test_fetcher_db.py       # Fetch → persist flow
│   └── test_monitor_alerts.py   # Monitor → alert flow
└── fixtures/
    └── mock_data.py             # Shared test data
```

---

## 9. Implementation Phases

### Phase 1 (MVP)
- PostgreSQL schema + ORM
- DataProvider adapter (MarketData.app)
- DataFetcher (daily + intraday + earnings + news)
- Basic scanner framework (price action, momentum, volume)
- Indicator library + caching
- RealtimeMonitor + alert rules
- CLI + log output
- Unit + integration tests

### Phase 2 (Enhancement)
- Options data + Greeks
- Database indicator caching (pre-compute daily)
- Multi-provider support (Finnhub, YahooFinance)
- Webhook output handler → dashboard integration
- Advanced alerts (Slack, email)
- Performance optimization (load testing, query optimization)

---

## 10. Key Design Decisions

1. **PostgreSQL over SQLite:** Time-series queries, concurrent realtime writes, BRIN indexing for latency
2. **Hybrid storage (local + realtime):** Daily/historical stored locally for backtesting, realtime fetched on-demand to save credits
3. **Adapter pattern for providers:** Swap MarketData.app without touching fetcher logic
4. **Shared indicator cache:** Eliminate recalculation within EOD run
5. **Output abstraction:** CLI/logs now, dashboard later without rearchitecture
6. **Modular scanner framework:** Add new scanners without touching executor
7. **Quote-level realtime data:** MarketData.app provides Level 1 quotes, sufficient for entry/exit logic
8. **Store all quote fields:** Intraday summary (open/high/low/52-week) provided at zero cost, enables richer logic

---

## 11. Success Criteria

- ✅ Sync 500 stocks daily within 1000 credits (target: 600-800)
- ✅ EOD scanner completes in < 5 minutes
- ✅ Realtime monitor polls 50 tickers at < 1 second latency
- ✅ Database queries < 100ms for 1-year candle history
- ✅ Scanner isolation: one fails, others continue
- ✅ Output abstraction supports CLI → dashboard upgrade with no core changes
- ✅ Unit test coverage > 80% for indicators & scanners
