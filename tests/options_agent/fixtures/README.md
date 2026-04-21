# Options Agent Test Fixtures

This directory contains synthetic golden fixtures for testing the options agent components.

## Directory Structure

```
fixtures/
├── chains/          # Options chain fixtures (JSON)
│   ├── aapl_2024-04-15.json
│   ├── spy_2024-04-15.json
│   └── tsla_2024-04-15.json
└── bars/            # Price bar fixtures with regime labels (CSV)
    ├── spy_jul2024_ranging.csv
    ├── aapl_oct2024_trending_up.csv
    └── nvda_aug2024_transitional.csv
```

## Chain Fixtures

Synthetic options chain data matching the Dolthub schema (`src/options_agent/data/dolt_client.py`).

### Schema

Each fixture is a JSON array of `OptionsContract` objects with:
- `symbol`: Underlying ticker
- `expiry_date`: Contract expiration (YYYY-MM-DD)
- `contract_type`: "C" (call) or "P" (put)
- `strike`: Strike price
- `bid`, `ask`, `mid`, `last`: Price data
- `volume`, `open_interest`: Liquidity metrics
- `iv`: Implied volatility (0-1)
- `delta`, `gamma`, `theta`, `vega`: Greeks

### Fixtures

| File | Characteristics |
|------|-----------------|
| `aapl_2024-04-15.json` | Moderate IV (~28%), near monthly expiry |
| `spy_2024-04-15.json` | Low IV (~14%), highly liquid |
| `tsla_2024-04-15.json` | High IV (~52%), earnings eve scenario |

## Bar Fixtures

Synthetic OHLCV price data (500 bars each) classified by market regime.

### Format

CSV files with comment headers (lines starting with `#`):
- `date`: Trading date (YYYY-MM-DD)
- `open`, `high`, `low`, `close`: OHLC prices
- `volume`: Trading volume

### Regime Classifications

Based on `src/options_agent/signals/regime.py` detection logic:
- **Ranging**: ADX < 20 AND ATR% < 0.015
- **Trending**: ADX > 25 AND ATR% <= 0.03
- **Transitional**: Neither trending nor ranging (catch-all)

| File | Regime | Direction | ADX | ATR% | Characteristics |
|------|--------|-----------|-----|------|-----------------|
| `spy_jul2024_ranging.csv` | ranging | neutral | ~14 | ~0.01 | Low volatility, price bound in 5% band |
| `aapl_oct2024_trending_up.csv` | trending | bullish | ~81 | ~0.028 | Strong momentum (70% up days) |
| `nvda_aug2024_transitional.csv` | transitional | unclear | ~15 | ~0.024 | Shifts from ranging to trending |

## Usage

### Loading Fixtures in Tests

```python
import pandas as pd
import json

# Load bar fixture (skip comment lines)
bars = pd.read_csv("tests/options_agent/fixtures/bars/spy_jul2024_ranging.csv", comment="#")

# Load chain fixture
with open("tests/options_agent/fixtures/chains/aapl_2024-04-15.json") as f:
    contracts = [OptionsContract(**c) for c in json.load(f)]
```

### Golden Tests

See `tests/options_agent/integration/test_regime_golden.py` for examples of using these fixtures in parametrized tests.

## Notes

- **Synthetic Data**: These fixtures are synthetic but realistic. They don't represent actual historical market data.
- **Purpose**: Designed for testing regime detection, chain analysis, and options signal generation.
- **Maintenance**: When updating regime detection logic, verify these fixtures still produce expected classifications.
- **Extending**: To add new fixtures, follow the existing patterns and document expected regime characteristics.
