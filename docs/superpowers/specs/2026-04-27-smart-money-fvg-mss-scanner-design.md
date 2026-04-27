# Smart Money FVG/MSS Scanner Design

**Date:** 2026-04-27
**Author:** Claude Code
**Status:** Approved

## Overview

Add an ICT-style price action scanner to the EOD pipeline that detects Fair Value Gaps (FVG), Break of Structure (BOS), and Market Structure Shift (MSS) entries on daily candles. The scanner identifies institutional footprint via significant gaps (≥0.75%), confirms trend changes via MSS, and signals entries only when price retraces 50-79% into the FVG zone.

## Architecture

### New Components

```
src/scanner/indicators/patterns/fvg.py
├── FVGDetector           # Detects and merges 3-candle FVGs
└── FractalSwings         # Identifies 5-bar fractal swing highs/lows

src/scanner/scanners/smart_money.py
└── SmartMoneyScanner     # Orchestrates FVG + swing + MSS detection
```

### Scanner Flow

```
1. Get last 100+ daily candles (need history for swing detection)
2. Detect all swing highs/lows using 5-bar fractal
3. Detect all FVGs (bullish + bearish)
4. Merge overlapping FVGs into zones
5. Filter by minimum gap size (≥0.75%)
6. Check for unmitigated FVGs
7. Detect BOS (price breaks swing high/low)
8. Detect MSS (retest of broken swing with close beyond)
9. Check if price is in 50-79% FVG zone
10. If MSS confirmed + in zone → Return match
```

### Integration

- Registers as `"smart_money"` in `ScannerRegistry`
- Runs automatically with existing `eod` command
- Results stored in `scanner_results` table
- Watchlist auto-generated after each EOD run

## FVG Detection & Merging

### FVG Identification (3-Candle Pattern)

**Bullish FVG (gap up):**
```python
candle[i].high < candle[i+2].low
Zone: (candle[i].high, candle[i+2].low)
```

**Bearish FVG (gap down):**
```python
candle[i].low > candle[i+2].high
Zone: (candle[i+2].high, candle[i].low)
```

### Minimum Gap Threshold

```python
gap_size_pct = abs(fvg.top - fvg.bottom) / fvg.bottom * 100
Minimum: 0.75%
```

Filters out random noise, captures only institutional-sized gaps.

### FVG Mitigation Check

```python
# Bullish FVG mitigated: any candle.close < FVG.bottom
# Bearish FVG mitigated: any candle.close > FVG.top
```

### FVG Merging (Overlapping Zones)

```python
# Two FVGs overlap if:
max(fvg1.bottom, fvg2.bottom) < min(fvg1.top, fvg2.top)

# Merged zone:
top: max(fvg1.top, fvg2.top)
bottom: min(fvg1.bottom, fvg2.bottom)
```

Prevents duplicate signals for adjacent gaps.

### Data Structure

```python
@dataclass
class FVGZone:
    top: float          # Zone top price
    bottom: float       # Zone bottom price
    bullish: bool       # True = bullish gap, False = bearish
    candle_index: int   # Index of candle that created FVG
    mitigated: bool     # Whether price has filled this gap
```

## Fractal Swing Detection

### Swing High Detection (5-Bar Fractal)

```python
candle[i].high is swing high if:
  candle[i-2].high < candle[i].high and
  candle[i-1].high < candle[i].high and
  candle[i].high > candle[i+1].high and
  candle[i].high > candle[i+2].high
```

### Swing Low Detection (5-Bar Fractal)

```python
candle[i].low is swing low if:
  candle[i-2].low > candle[i].low and
  candle[i-1].low > candle[i].low and
  candle[i].low < candle[i+1].low and
  candle[i].low < candle[i+2].low
```

### Data Structure

```python
@dataclass
class SwingPoint:
    price: float           # Swing high or low price
    is_high: bool         # True = swing high, False = swing low
    candle_index: int     # Index in candle array
    timestamp: datetime   # Candle timestamp
```

## BOS/MSS Detection

### Break of Structure (BOS)

```python
# Bullish BOS: Price closes above most recent swing high
latest_close > recent_swing_high.price

# Bearish BOS: Price closes below most recent swing low
latest_close < recent_swing_low.price
```

### Market Structure Shift (MSS) Confirmation

After BOS, price must retest and **close** beyond the broken swing level:

**Bullish MSS:**
1. Price breaks swing high (BOS)
2. Price retraces back
3. Candle closes **below** the broken swing high
→ Confirms bulls defended the breakout

**Bearish MSS:**
1. Price breaks swing low (BOS)
2. Price retraces back
3. Candle closes **above** the broken swing low
→ Confirms bears defended the breakdown

### MSS Detection Window

Only look for MSS within the last 20 candles after BOS.
Prevents stale signals from old structure breaks.

### State Tracking

```python
@dataclass
class MSSState:
    bos_type: str          # "bullish" or "bearish"
    bos_candle_index: int  # When BOS occurred
    broken_swing_price: float  # The swing level that broke
    mss_confirmed: bool    # Whether MSS has occurred
    mss_candle_index: int | None  # When MSS confirmed (if applicable)
```

## Entry Signal Generation

### Fibonacci Retracement Zones

```python
fvg_height = fvg.top - fvg.bottom

fib_50 = fvg.top - (fvg_height * 0.50)
fib_618 = fvg.top - (fvg_height * 0.618)
fib_79 = fvg.top - (fvg_height * 0.79)

# Entry zone: Between fib_79 and fib_50
```

### Entry Conditions (All Must Be True)

1. **Unmitigated FVG exists** (gap ≥ 0.75%)
2. **MSS confirmed** (close beyond broken swing)
3. **Current price in 50-79% zone**:
   - `fib_79 <= current_close <= fib_50`
4. **MSS occurred after FVG formation** (entry on fresh setup)

### Signal Metadata

```python
metadata = {
    "reason": "fvg_mss_entry",
    "fvg_top": fvg.top,
    "fvg_bottom": fvg.bottom,
    "fvg_size_pct": gap_size_pct,
    "entry_price": current_close,
    "fib_zone": "50-79%",
    "fib_50": fib_50,
    "fib_618": fib_618,
    "fib_79": fib_79,
    "mss_type": "bullish" | "bearish",
    "bos_price": broken_swing_price,
    "mss_confirm_bar": mss_candle_index,
}
```

## Error Handling & Edge Cases

### Insufficient Data

```python
if len(context.daily_candles) < 100:
    return []  # Skip stock
```

### No Valid Swings

```python
if len(swing_highs) < 3 or len(swing_lows) < 3:
    return []  # Insufficient market structure
```

### No Valid FVGs

```python
# No gaps ≥ 0.75% detected
if len(valid_fvgs) == 0:
    return []
```

### All FVGs Mitigated

```python
if all(fvg.mitigated for fvg in detected_fvgs):
    return []
```

### MSS Not Yet Confirmed

```python
# FVG exists and BOS occurred, but waiting for MSS
# → Don't return match (incomplete setup)
```

### Overmerged FVG (Too Wide)

```python
# After merging, if zone > 5% of price, skip
# → Too wide = unclear institutional footprint
if (merged_fvg.top - merged_fvg.bottom) / merged_fvg.bottom > 0.05:
    continue
```

## Configuration Constants

```python
MIN_FVG_GAP_PCT = 0.75      # Minimum gap size (%)
MAX_MERGED_ZONE_PCT = 5.0   # Max merged zone size (%)
MSS_LOOKBACK = 20           # Max candles to confirm MSS
MIN_CANDLES = 100           # Minimum candles for swing detection
```

## Testing Strategy

### Unit Tests

```
tests/unit/test_fvg_indicator.py
├── test_bullish_fvg_detection
├── test_bearish_fvg_detection
├── test_fvg_below_threshold_filtered
├── test_fvg_merging_overlapping_zones
└── test_fvg_mitigation_detection

tests/unit/test_fractal_swings.py
├── test_swing_high_detection
├── test_swing_low_detection
├── test_swing_sequencing
└── test_insufficient_candles_handling

tests/unit/test_smart_money_scanner.py
├── test_bos_detection
├── test_mss_confirmation_bullish
├── test_mss_confirmation_bearish
├── test_fib_retracement_calculation
├── test_entry_signal_all_conditions_met
├── test_no_signal_without_mss
├── test_no_signal_outside_fib_zone
└── test_edge_cases
```

### Integration Tests

```
tests/integration/test_smart_money_e2e.py
├── test_full_scanner_pipeline_with_mock_data
├── test_scanner_registration_and_execution
└── test_watchlist_generation_from_scanner_results
```

### Test Data

- Historical candles with known FVG/MSS patterns
- Fixture data for bullish/bearish scenarios
- Edge case data (small gaps, mitigated FVGs, incomplete setups)

## File Structure

### New Files

```
src/scanner/indicators/patterns/
├── __init__.py          # Update: export FVGDetector, FractalSwings
└── fvg.py               # New: FVG detection + swing detection

src/scanner/scanners/
├── __init__.py          # Update: export SmartMoneyScanner
└── smart_money.py       # New: Main scanner logic

tests/unit/
├── test_fvg_indicator.py
├── test_fractal_swings.py
└── test_smart_money_scanner.py

tests/integration/
└── test_smart_money_e2e.py
```

### Scanner Registration

In `src/main.py`:

```python
from src.scanner.scanners.smart_money import SmartMoneyScanner

scanner_registry.register("smart_money", SmartMoneyScanner())
```

## Scanner Metadata

```python
SmartMoneyScanner.timeframe = "daily"
SmartMoneyScanner.description = "ICT-style FVG + MSS entry detection (50-79% zone)"
```

## Implementation Notes

- **Performance:** Scanning 500 stocks × ~100 candles each = ~50K candles processed per EOD run. Should complete in < 5 seconds.
- **Memory:** FVG and swing state stored per scan, no persistence needed between runs.
- **Backward compatibility:** No database schema changes required. Uses existing `scanner_results` table.
- **Extensibility:** Can add volume confirmation, ATR filters, or multi-timeframe confluence later.

## Success Criteria

- Scanner runs without errors on EOD pipeline
- Returns matches only when all 4 entry conditions are met
- Generates watchlists automatically after each EOD run
- Unit test coverage > 80%
- Integration test passes with mock historical data
- No performance degradation in existing EOD pipeline
