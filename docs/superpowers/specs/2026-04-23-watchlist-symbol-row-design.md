# Watchlist Symbol Row Visual Enhancement — Design Spec

**Date:** 2026-04-23
**Status:** Approved
**Focus:** Left pane (watchlist panel) symbol row design

---

## Problem

The current symbol row shows price data but lacks visual context for traders:
- No trend information — can't tell if a stock is gaining momentum or selling off
- No range context — can't see where current price sits within today's high/low
- Requires clicking the chart to assess tradeability

Traders need a visual filter to quickly assess:
1. Is this trending up or down?
2. Where is the price within today's range?
3. Was there intraday volatility or a clean trend?

---

## Solution: Dual Visual Indicators

Each symbol row gets TWO compact visual elements:

### 1. Sparkline (48px × 16px)
- **What:** Mini line chart showing intraday price path
- **Data:** Last 20-30 intraday data points (1h candles or current day candle overlay)
- **Color:** Green if close > open, Red if close < open, Gray if flat
- **Shows:** Trend direction, volatility, reversals (V-shape = dip bought, Λ-shape = rally rejected)

### 2. Range Bar with Position Dot (32px × 14px)
- **What:** Horizontal gradient bar with vertical line marking current price
- **Gradient:** Red (low) → Yellow (middle) → Green (high) at 50% opacity
- **Dot:** 2px vertical yellow line with glow, positioned at current price % within range
- **Shows:** Where close sits within today's low/high (support/resistance proximity)

---

## Layout

```
┌─────────────────────────────────────────────────────────┐
│ dot | ticker | spark | range | last | chg% | ×           │
│ 10px | 38px |  48px | 32px | 40px | 40px | 12px        │
└─────────────────────────────────────────────────────────┘
Total: ~244px + gaps = fits in 260px pane
```

**Column specifications:**
- `dot` — Source indicator (● realtime, ○ EOD)
- `ticker` — Symbol, bold weight
- `spark` — SVG polyline, 48px wide
- `range` — Gradient bar with position dot, 32px wide
- `last` — Current price, bold, right-aligned
- `chg%` — Percent change, colored (green/red), right-aligned
- `×` — Remove button, visible on hover

**Changes from current:**
- Remove `$ change` column (redundant with %)
- Compress column gaps from 6px → 4px
- Shrink ticker column from 48px → 38px

---

## Visual Examples

### Strong Uptrend
```
● AAPL [╱] [▮───────] 186.59 +5.01% ✕
        spark  range
```
Sparkline climbs steadily, range dot near right → opened strong, stayed strong all day

### Dip Then Recovery
```
● TSLA [╲╱] [───▮───] 245.30 +1.20% ✕
        spark  range
```
V-shape sparkline, range dot mid-upper → intraday dip was bought, recovered

### Sold Off All Day
```
○ CVNA [╲] [▮──────] 358.55 -3.38% ✕
        spark  range
```
Sparkline falls, range dot near left → opened weak, sold off to lows

### Rangebound
```
○ GSAT [∿∿] [────▮───] 79.85 -0.05% ✕
        spark  range
```
Jagged sparkline, range dot centered → choppy, no trend

---

## Data Requirements

### For Sparkline
- **Source:** Existing intraday candles (1h resolution) OR current day candle overlay
- **Points:** Last 20-30 data points for the current market day
- **Fallback:** If intraday unavailable, render gray horizontal line
- **Format:** Array of `{ time, close }` values

### For Range Bar
- **Source:** Already available in `QuoteResponse` (last, low, high)
- **Calculation:** `position = (last - low) / (high - low) * 100%`
- **Edge case:** If low === high, center the dot at 50%

---

## Component Changes

### Files Modified
| File | Change |
|------|--------|
| `frontend/src/pages/watchlists/symbol-row.tsx` | Add sparkline SVG + range bar |
| `frontend/src/pages/watchlists/types.ts` | Add `intraday: { time, close }[]` to QuoteResponse |
| `frontend/src/lib/watchlists-api.ts` | Fetch intraday data with quotes |
| `src/api/watchlists/routes.py` | Add intraday data to quotes response |
| `src/api/watchlists/schemas.py` | Add intraday field to QuoteResponse schema |
| `src/api/watchlists/service.py` | Fetch intraday candles for quotes |

### New: Sparkline Component
```tsx
// frontend/src/pages/watchlists/sparkline.tsx
interface SparklineProps {
  data: { time: string; close: number }[];
  color: 'green' | 'red' | 'gray';
  width: number;
  height: number;
}
```

Renders an SVG polyline from normalized data points.

### New: RangeBar Component
```tsx
// frontend/src/pages/watchlists/range-bar.tsx
interface RangeBarProps {
  low: number;
  high: number;
  current: number;
  width: number;
  height: number;
}
```

Renders gradient background with position marker.

---

## Color Specification

| Element | Bullish | Bearish | Neutral |
|---------|---------|---------|---------|
| Sparkline line | `#22c55e` | `#ef4444` | `#94a3b8` |
| Range gradient | Red→Yellow→Green (fixed) | Same | Same |
| Position dot | `#fbbf24` | `#fbbf24` | `#fbbf24` |
| Dot glow | `box-shadow: 0 0 3px #fbbf24` | Same | Same |

---

## Responsive Behavior

- Desktop (current pane width: 260px): Show full layout
- If pane width < 240px: Hide sparkline first, then range bar
- Mobile: Out of scope for this spec

---

## Performance Considerations

- Sparkline uses SVG — cheap to render, scales cleanly
- Intraday data fetched with quotes (single API call)
- Data cached per quote refresh cycle
- SVG polyline with ~20 points is negligible render cost

---

## Accessibility

- Sparkline and range bar are decorative — include `aria-hidden="true"`
- Screen readers still get full data: ticker, last price, change %
- Color is NOT the only indicator — dot position, slope both convey meaning

---

## Out of Scope

- Right pane chart enhancements (separate discussion)
- Mobile layout
- Historical sparklines (multi-day)
- Volume sparkline
- Interactivity on sparkline (tooltips, hover states)

---

## Success Criteria

1. Trader can assess trend direction at a glance without clicking chart
2. Trader can see if price is near support (low) or resistance (high)
3. Layout fits within 260px pane without horizontal scrolling
4. Visuals render performantly with 500+ symbols
5. EOD symbols show gray fallback for sparkline (no intraday data)

---

## Reference: Industry Usage

- **Bloomberg Terminal**: 1-day sparklines (64×20 SVG) on every quote row
- **TradingView**: Sparkline option in watchlist advanced view
- **Finviz**: Mini-charts on screener results

This design follows established patterns used by professional trading platforms.
