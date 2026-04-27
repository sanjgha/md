# Six-Month High Scanner Design

**Date:** 2026-04-27
**Status:** Approved
**Author:** Claude Code

## Overview

Add a new scanner to detect stocks whose daily **close price** has reached the highest level seen in the past 126 trading days (approximately 6 months), occurring within the last 5 trading days. Only the most recent occurrence is reported per stock.

## Architecture

### Component: SixMonthHighScanner

- Inherits from `Scanner` base class
- Uses new `rolling_max` indicator for 126-period rolling maximum
- Checks last 5 trading days for new 6-month highs
- Returns most recent match as `ScanResult`

### Data Requirements

- Minimum 131 daily candles per stock (126 for reference window + 5 for lookback)
- Stocks with fewer candles are skipped (empty result)

### Match Output

```python
ScanResult(
    stock_id=context.stock_id,
    scanner_name="six_month_high",
    metadata={
        "six_month_high": 245.50,      # The 6-month high price (from rolling_max[-6])
        "current_close": 247.30,        # Price that broke it
        "days_ago": 2,                  # Days ago: 0=today (index -1), 1=yesterday (index -2), etc.
        "high_date": "2026-04-25"       # Date from candle timestamp
    }
)
```

## Components

### New Files

1. **`src/scanner/indicators/rolling_max.py`**
   - `RollingMax` class implementing `Indicator` interface
   - `compute(candles, period)` returns numpy array of rolling maximum closes

2. **`src/scanner/scanners/six_month_high.py`**
   - `SixMonthHighScanner` class with `scan(context)` method
   - Timeframe: daily
   - Description: "Stocks that hit 6-month high (close) in past 5 trading days"

### Modified Files

1. **`src/scanner/scanners/__init__.py`**
   - Add import: `from src.scanner.scanners.six_month_high import SixMonthHighScanner`
   - Add to `__all__`

2. **`src/scanner/indicators/__init__.py`**
   - Add import for `RollingMax` if not auto-imported

## Algorithm

### Execution Flow

```
For each stock in universe:
  1. Load last 131+ daily candles
  2. Create ScanContext with candles
  3. Call SixMonthHighScanner.scan(context)
```

### Scanner Logic

```
1. Validate: if len(candles) < 131: return []

2. Compute rolling_max(126):
   - Returns array where each value = max close in last 126 periods
   - Example: candles[0..125] → max1, candles[1..126] → max2, etc.

3. Get reference high: six_month_high = rolling_max[-6]
   (Index -6 = 6-month high as of 6 days ago, before lookback window)

4. Check last 5 candles:
   For i in range(-5, 0):  # indices -5, -4, -3, -2, -1
       if candles[i].close > six_month_high:
           Record match at position i

5. If multiple matches, keep only most recent (largest i, closest to -1)

6. Return ScanResult with metadata
```

### Why Index -6?

The rolling_max at position `-6` represents the highest close in the 126 days ending 6 days ago. Any close in the last 5 days that exceeds this is a new 6-month high.

## Error Handling

Follows existing patterns from `PriceActionScanner` and `MomentumScanner`:

1. **Insufficient data:** Return empty list (not an error)
2. **Calculation errors:** Wrap in try/except, log exception, return empty list
3. **Edge cases:**
   - Exactly 131 candles: works (boundary case)
   - Fewer than 131: skipped
   - Multiple new highs in 5-day window: only most recent returned
   - No new high: empty result

## Testing

### Unit Test: `tests/unit/test_six_month_high_scanner.py`

Test cases:
1. **Match found** — Stock hits 6-month high 3 days ago
2. **Multiple matches** — New highs on days 1, 3, 5 → returns only day 5
3. **No match** — Price stays below 6-month high
4. **Insufficient data** — Only 100 candles → empty result
5. **Boundary case** — Exactly 131 candles → works correctly
6. **Flat/declining price** — No new high → empty result

Use mock candles (fast unit test, no testcontainers needed).

Example test data:
```python
# Candles 0-125: Various prices, max = 200.00
# Candles 126-130: [195, 198, 201, 203, 205]
# Expected: Match at candle 128 (close=201) is first, but candle 130 (close=205) is most recent
# Result: Returns match at index -1 (candle 130), days_ago=0, high_date=today
```

### Integration Testing

No dedicated integration test needed. Scanner executor integration tests in `tests/integration/` provide coverage for the scanning pipeline.

## Implementation Notes

- Use pandas `rolling(max)` or pure numpy for `rolling_max` indicator
- Follow existing code patterns in `PriceActionScanner` for structure
- Register scanner in `ScannerRegistry` during initialization
- Log failures per stock without failing entire scan run
