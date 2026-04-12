# MarketData.app Reference Guide

**Last Updated:** 2026-04-04  
**Purpose:** Complete reference for marketdata.app API capabilities, endpoints, data depth, feeds, and latency considerations

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Data Coverage & Asset Classes](#data-coverage--asset-classes)
4. [API Endpoints](#api-endpoints)
5. [Fundamental Analysis & Earnings Data](#fundamental-analysis--earnings-data)
6. [Data Feeds & Latency](#data-feeds--latency)
7. [Data Depth & Historical Coverage](#data-depth--historical-coverage)
8. [Pricing Plans & Rate Limits](#pricing-plans--rate-limits)
9. [Response Formats](#response-formats)
10. [Implementation Considerations](#implementation-considerations)
11. [Quick Reference: Common API Calls](#quick-reference-common-api-calls)
12. [SDKs & Language Integration](#sdks--language-integration)
13. [References & Additional Resources](#references--additional-resources)

---

## Overview

MarketData.app is a comprehensive market data provider offering real-time and historical pricing data for stocks, ETFs, mutual funds, indices, and options. The API is built on REST principles with JSON and CSV response formats.

**Key Features:**
- Real-time quotes from IEX (stocks) and OPRA (options)
- Decades of historical pricing data
- Multiple data feed types (live, cached, delayed)
- Flexible API with universal parameters
- Google Sheets integration via formulas
- Free trial + free tier with 100 requests/day

**Official Resources:**
- [MarketData.app Home](https://www.marketdata.app/)
- [API Documentation](https://www.marketdata.app/docs/api/)
- [GitHub Documentation Repo](https://github.com/MarketData-App/documentation)

---

## Authentication

### Header-Based Authentication (Recommended)

```
Authorization: Bearer YOUR_API_TOKEN
```

**Best Practices:**
- Use header-based auth to prevent token caching
- Add token to the Authorization header with "Bearer" prefix
- Free accounts and trial accounts can experiment with AAPL ticker without authentication

**Access Levels:**
- **Free/Trial:** Delayed data only (15+ minutes old)
- **Paid Plans:** Feed parameter control (live, cached, delayed)

---

## Data Coverage & Asset Classes

### Supported Assets

| Asset Class | Coverage | Real-Time Source | Historical Depth |
|---|---|---|---|
| **Stocks** | All U.S.-traded stocks | IEX Exchange | Decades of daily data |
| **ETFs** | All U.S.-traded ETFs | IEX Exchange | Decades of daily data |
| **Options** | U.S.-listed equity, ETF, index options | OPRA (All exchanges) | EOD data back to 2010 |
| **Indices** | Major market indices | IEX | Decades of data |
| **Mutual Funds** | U.S.-listed mutual funds | Various | Historical data available |

### Options Data Note

Real-time options data aggregates feeds from:
- Chicago Board Options Exchange (Cboe)
- New York Stock Exchange (NYSE)
- Nasdaq

**Important Limitation:** No intraday options history or futures options data available.

---

## API Endpoints

### Stock Quotes

**Endpoint:** `GET /v1/stocks/quotes/{symbol}/`

**Purpose:** Fetch real-time Level 1 stock quote (top of book) for all U.S.-traded stocks and ETFs

**Required Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `symbol` | String | Stock ticker symbol (e.g., `AAPL`, `MSFT`) |

**Optional Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `feed` | String | `live`, `cached`, or `delayed` (paid plans only) |
| `format` | String | `json` or `csv` |

**Response Format:**
```json
{
  "s": "ok",
  "symbol": "AAPL",
  "ask": 150.30,
  "askSize": 1000,
  "bid": 150.20,
  "bidSize": 800,
  "last": 150.25,
  "mid": 150.25,
  "change": 2.50,
  "changepct": 1.69,
  "volume": 45320000,
  "o": 147.90,
  "h": 151.50,
  "l": 147.65,
  "c": 150.25,
  "52weekHigh": 199.62,
  "52weekLow": 124.17,
  "updated": "2026-04-04T16:00:00Z",
  "status": "active"
}
```

**Response Fields:**
- **s** - Status: `ok`, `no_data`, or `error`
- **symbol** - Stock ticker symbol
- **bid** - Best bid price
- **ask** - Best ask price
- **bidSize** - Size at bid
- **askSize** - Size at ask
- **last** - Last traded price
- **mid** - Midpoint of bid-ask spread
- **change** - Absolute price change from previous close
- **changepct** - Percentage price change from previous close
- **volume** - Current trading volume
- **o** - Opening price for the trading day
- **h** - High price for the trading day
- **l** - Low price for the trading day
- **c** - Closing price from previous trading day
- **52weekHigh** - 52-week high price
- **52weekLow** - 52-week low price
- **updated** - Timestamp of last update
- **status** - Quote status indicator

**Example Requests:**

```
GET https://api.marketdata.app/v1/stocks/quotes/AAPL/
```

Free tier - no authentication required.

```
GET https://api.marketdata.app/v1/stocks/quotes/MSFT/?feed=live
Authorization: Bearer YOUR_TOKEN
```

Real-time quote with paid plan.

**Free Tier:** AAPL ticker available without authentication. Paid plans unlock real-time data for all symbols.

---

### Stock Candles (OHLCV Bars)

**Endpoint:** `GET /v1/stocks/candles/{resolution}/{symbol}/`

**Purpose:** Fetch historical OHLC(V) data at specified resolution

**Supported Resolutions:**
- **Minutely:** `1`, `3`, `5`, `15`, `30`, `45` (minutes)
- **Hourly:** `H`, `1H`, `2H`, `4H`, `8H`
- **Daily/Longer:** `D`, `1D`, `W`, `M`, `Y`
- Case-insensitive

**Required Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `resolution` | String | Candle duration (e.g., `1d`, `5m`, `1h`) |
| `symbol` | String | Stock ticker symbol (e.g., `AAPL`) |

**Optional Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `from` | Date | Start date (ISO 8601, Unix timestamp, or spreadsheet format); mutually exclusive with `countback` |
| `to` | Date | End date (same format as `from`) |
| `countback` | Integer | Number of candles to fetch before the `to` date; mutually exclusive with `from` |
| `extended` | Boolean | Include extended hours for intraday candles (default: false) |
| `adjustsplits` | Boolean | Adjust for stock splits (default: true for daily, false for intraday) |
| `format` | String | `json` or `csv` |
| `limit` | Integer | Max results per call |
| `offset` | Integer | Pagination offset |

**Response Format:**
```json
{
  "s": "ok",
  "c": [217.68, 221.03, 219.89],
  "h": [222.49, 221.5, 220.94],
  "l": [217.19, 217.1402, 218.83],
  "o": [221.03, 218.55, 220],
  "t": [1569297600, 1569384000, 1569470400],
  "v": [33463820, 24018876, 20730608]
}
```

**Response Fields:**
- **s** - Status: `ok`, `no_data`, or `error`
- **o** - Array of opening prices
- **h** - Array of high prices
- **l** - Array of low prices
- **c** - Array of closing prices
- **v** - Array of volumes
- **t** - Array of Unix timestamps (UTC for intraday; midnight Eastern for daily+)

**Example Requests:**

```
GET https://api.marketdata.app/v1/stocks/candles/1d/AAPL/?from=2020-01-01&to=2020-12-31
Authorization: Bearer YOUR_TOKEN
```

```
GET https://api.marketdata.app/v1/stocks/candles/5m/AAPL/?countback=50
Authorization: Bearer YOUR_TOKEN
```

**Data Limitations:** 
- Intraday requests cannot exceed 1 year of data per request
- Data through previous trading day only (not current day intraday)

---

### Bulk Quotes

**Endpoint:** `GET /v1/stocks/bulkquotes`

**Purpose:** Fetch quotes for multiple symbols in a single request (cost-effective)

**Required Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `symbols` | String | Comma-separated list of stock symbols (e.g., `AAPL,MSFT,GOOGL`) |

**Optional Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `feed` | String | `live`, `cached`, or `delayed` (paid plans only) |
| `format` | String | `json` or `csv` |

**Response Format:**
```json
{
  "s": "ok",
  "results": [
    {
      "symbol": "AAPL",
      "ask": 150.30,
      "askSize": 1000,
      "bid": 150.20,
      "bidSize": 800,
      "last": 150.25,
      "mid": 150.25,
      "updated": "2026-04-04T16:00:00Z"
    },
    {
      "symbol": "MSFT",
      "ask": 425.50,
      "askSize": 500,
      "bid": 425.40,
      "bidSize": 600,
      "last": 425.45,
      "mid": 425.45,
      "updated": "2026-04-04T16:00:00Z"
    }
  ]
}
```

**Example Requests:**

```
GET https://api.marketdata.app/v1/stocks/bulkquotes?symbols=AAPL,MSFT,GOOGL
Authorization: Bearer YOUR_TOKEN
```

```
GET https://api.marketdata.app/v1/stocks/bulkquotes?symbols=AAPL,MSFT,GOOGL&feed=cached
Authorization: Bearer YOUR_TOKEN
```

**Use Case:** Cost-effective way to fetch quotes for many symbols at once. Bulk endpoint reduces per-symbol overhead compared to individual quote requests.

---

### Options Quotes

**Endpoint:** `GET /v1/options/quotes/{optionSymbol}/`

**Purpose:** Fetch real-time or historical option quotes with pricing and Greeks

**Real-Time Source:** OPRA consolidated feed (all exchanges)

**Historical:** End-of-day quotes back to 2010

**Required Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `optionSymbol` | String | OCC-formatted option symbol (e.g., `AAPL271217C00250000`) |

**Optional Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `date` | Date | Historical end-of-day quote from specific trading day |
| `from` | Date | Start date for date range (ISO 8601, Unix timestamp, or spreadsheet format) |
| `to` | Date | End date for date range |
| `feed` | String | `live`, `cached`, or `delayed` (paid plans only) |
| `format` | String | `json` or `csv` |

**Response Includes:**
- Price data: ask, bid, mid, last prices with sizes
- Volume metrics: trading volume and open interest
- Greeks: delta, gamma, theta, vega, and implied volatility
- Option details: underlying price, intrinsic/extrinsic values
- Status indicator

**Example Request:**
```
GET https://api.marketdata.app/v1/options/quotes/AAPL271217C00250000/?feed=live
Authorization: Bearer YOUR_TOKEN
```

**Example Response:**
```json
{
  "s": "ok",
  "ask": 2.50,
  "askSize": 500,
  "bid": 2.45,
  "bidSize": 1000,
  "last": 2.48,
  "mid": 2.475,
  "volume": 15230,
  "openInterest": 8500,
  "delta": 0.65,
  "gamma": 0.08,
  "theta": -0.12,
  "vega": 0.18,
  "iv": 0.35,
  "underlyingPrice": 250.75,
  "intrinsicValue": 0.75,
  "extrinsicValue": 1.73
}
```

**Pricing:**
- Real-time quotes: 1 credit per symbol
- 15-minute delayed: 1 credit per symbol
- Historical data: 1 credit per 1,000 quotes

---

### Stock News

**Endpoint:** `GET /v1/stocks/news/{symbol}/`

**Purpose:** Fetch news articles for a specific stock

**Required Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `symbol` | String | Stock ticker symbol (e.g., `AAPL`, `MSFT`) |

**Optional Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `from` | Date | Earliest news date (ISO 8601, Unix timestamp, or spreadsheet format) |
| `to` | Date | Latest news date (same format as `from`) |
| `countback` | Integer | Number of articles to fetch before the `to` date |
| `date` | Date | Retrieve news for a specific day |
| `format` | String | `json` or `csv` |

**Response Format:**
```json
{
  "s": "ok",
  "symbol": ["AAPL", "AAPL"],
  "headline": ["Apple Q2 Earnings Beat Expectations", "Apple Announces New Product Line"],
  "content": ["Apple reported record quarterly earnings...", "In a surprise announcement..."],
  "source": ["reuters.com", "bloomberg.com"],
  "publicationDate": ["2026-04-03T15:30:00Z", "2026-04-02T10:15:00Z"],
  "updated": "2026-04-04T16:00:00Z"
}
```

**Response Fields:**
- **s** - Status: `ok`, `no_data`, or `error`
- **symbol** - Array of ticker symbols mentioned in articles
- **headline** - Array of article titles
- **content** - Array of article text/summaries
- **source** - Array of source URLs where articles appeared
- **publicationDate** - Array of publication timestamps

**Example Requests:**

```bash
curl -X GET "https://api.marketdata.app/v1/stocks/news/AAPL/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Get recent news for AAPL.

```bash
curl -X GET "https://api.marketdata.app/v1/stocks/news/MSFT/?from=2026-03-01&to=2026-04-04" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Get news within a specific date range.

```bash
curl -X GET "https://api.marketdata.app/v1/stocks/news/GOOGL/?countback=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Get last 10 news articles.

**Pricing:** 1 credit per API call

**Note:** Currently in beta - may have performance considerations for production use.

---

### Stock Earnings

**Endpoint:** `GET /v1/stocks/earnings/{symbol}/`

**Purpose:** Fetch historical and upcoming earnings data with EPS estimates and actual results

**Required Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `symbol` | String | Stock ticker symbol (e.g., `AAPL`, `MSFT`) |

**Optional Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `from` | Date | Earliest earnings report date (ISO 8601, Unix timestamp, or spreadsheet format) |
| `to` | Date | Latest earnings report date (same format as `from`) |
| `countback` | Integer | Number of earnings reports to fetch before the `to` date |
| `date` | Date | Retrieve a specific earnings report by date |
| `format` | String | `json` or `csv` |

**Response Format:**
```json
{
  "s": "ok",
  "symbol": "AAPL",
  "fiscalYear": 2026,
  "fiscalQuarter": 2,
  "date": "2026-04-23",
  "reportDate": "2026-04-23T16:30:00Z",
  "reportTime": "after market close",
  "currency": "USD",
  "reportedEPS": 1.95,
  "estimatedEPS": 1.92,
  "surpriseEPS": 0.03,
  "surpriseEPSpct": 1.56,
  "updated": "2026-04-04T16:00:00Z"
}
```

**Response Fields:**
- **s** - Status: `ok`, `no_data`, or `error`
- **symbol** - Company ticker symbol
- **fiscalYear** - Fiscal year of the report
- **fiscalQuarter** - Fiscal quarter (1-4)
- **date** - Calendar date of earnings report
- **reportDate** - Actual/estimated release date and time
- **reportTime** - Timing: "before market open", "after market close", or "during market hours"
- **currency** - Currency of EPS values
- **reportedEPS** - Actual earnings per share reported
- **estimatedEPS** - Wall Street analyst consensus estimate
- **surpriseEPS** - Absolute difference (reported - estimated)
- **surpriseEPSpct** - Percent difference between reported and estimated EPS
- **updated** - Last data update timestamp

**Example Requests:**

```bash
curl -X GET "https://api.marketdata.app/v1/stocks/earnings/AAPL/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Get all available earnings reports for AAPL.

```bash
curl -X GET "https://api.marketdata.app/v1/stocks/earnings/MSFT/?countback=4" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Get last 4 earnings reports (most recent earnings).

```bash
curl -X GET "https://api.marketdata.app/v1/stocks/earnings/GOOGL/?from=2024-01-01&to=2026-04-04" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Get earnings reports within a date range.

**Pricing:** 1 credit per API call

**Use Cases:**
- Earnings surprise analysis
- EPS estimates vs. actual tracking
- Earnings calendar and upcoming reports
- Fundamental analysis and valuation
- Trading strategy around earnings dates

---

### Option Chain

**Endpoint:** `GET /v1/options/chain/{symbol}`

**Purpose:** Fetch entire option chain for an underlying symbol with all calls and puts

**Required Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `symbol` | String | Underlying stock ticker (e.g., `AAPL`, `MSFT`) |

**Optional Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `date` | Date | Get chain for specific expiration date |
| `expiration` | String | Filter by expiration (YYYY-MM-DD format) |
| `strike` | Number | Filter by strike price |
| `dte` | Integer | Filter by days to expiration range |
| `delta` | Number | Filter by delta range |
| `type` | String | Filter by type: `call` or `put` |
| `format` | String | `json` or `csv` |

**Filterable By:**
- Expiration date
- Strike price
- Days to expiration (DTE)
- Delta ranges
- Option type (calls/puts)

**Example Requests:**

```
GET https://api.marketdata.app/v1/options/chain/AAPL/
Authorization: Bearer YOUR_TOKEN
```

Get full chain for all expirations and strikes.

```
GET https://api.marketdata.app/v1/options/chain/AAPL/?expiration=2026-05-15&type=call
Authorization: Bearer YOUR_TOKEN
```

Get call options expiring on May 15, 2026.

```
GET https://api.marketdata.app/v1/options/chain/MSFT/?delta=0.5&dte=30
Authorization: Bearer YOUR_TOKEN
```

Get options with ~0.5 delta and ~30 days to expiration.

**Use Cases:**
- Build option trading screens
- Volatility surface analysis
- Greeks calculations and hedging
- Risk management and portfolio analysis
- Options strategy screening

---

### Index Endpoints

**Purpose:** Access real-time and historical data for financial indices

**Includes:** Both quotes and historical data endpoints similar to stocks

---

## Fundamental Data & News

*Available on Starter plan ($12/month) and higher. Unlocks premium fundamental and news endpoints for comprehensive company and market analysis.*

### Availability by Plan

| Feature | Free | Starter+ |
|---|---|---|
| Earnings Data | AAPL only | All U.S. companies |
| News Articles | Limited | All U.S. companies |
| Historical Data | Limited | Full access |
| Data Cost | 1 credit/call | 1 credit/call |

**Note:** See the detailed [Stock Earnings](#stock-earnings) and [Stock News](#stock-news) sections in the API Endpoints for complete endpoint documentation and examples.

---

## Data Feeds & Latency

### Feed Types (Controlled via `feed` Parameter)

**Note:** Feed parameter only available on paid plans. Free/trial accounts receive delayed data by default.

#### 1. Live Feed (Real-Time)
- **Latency:** Milliseconds to seconds
- **Default Behavior:** Used if `feed` parameter omitted or `feed=live`
- **Best For:** Active trading, real-time alerts, high-frequency monitoring
- **Cost Impact:** Higher API credit consumption
- **Symbol Refresh:** All symbols updated as market moves

**Example:**
```
GET /v1/stocks/quotes/AAPL?feed=live
```

---

#### 2. Cached Feed
- **Latency:** 2-300 seconds (no guaranteed freshness)
- **Activation:** Add `feed=cached` to request
- **Best For:** Bulk data retrieval, historical analysis, cost optimization
- **Cost Impact:** Lower API credit consumption
- **Refresh Pattern:** Popular tickers refreshed more frequently than less-traded symbols
- **Consistency:** May return different data on repeated calls for same symbol

**Example:**
```
GET /v1/stocks/quotes/XYZ?feed=cached
```

---

#### 3. Delayed Feed
- **Latency:** 15+ minutes old
- **Default for:** Free and trial accounts
- **Activation:** Add `feed=delayed` to request (requires paid plan)
- **Best For:** End-of-day analysis, research, backtesting
- **Cost Impact:** Lowest API credit consumption
- **Use Case:** Compliance with real-time data restrictions

**Example:**
```
GET /v1/stocks/quotes/AAPL?feed=delayed
```

---

### Latency Considerations

| Use Case | Recommended Feed | Typical Latency | Data Freshness |
|---|---|---|---|
| Algorithmic Trading | Live | <1s | Current tick |
| Real-Time Monitoring | Live | 1-5s | Current |
| Position Management | Cached | 5-60s | Recent |
| End-of-Day Analysis | Delayed | 15+ min | EOD closing |
| Historical Backtesting | Any | N/A | Historical only |
| Bulk Data Sync | Cached | N/A | Variable |

### Cost Optimization Strategy

- Use **cached feed** for bulk operations to reduce credit consumption
- Use **live feed** only for latency-sensitive operations
- Batch requests with **bulk endpoints** when fetching multiple symbols
- Implement client-side caching with invalidation timers
- Consider historical data for research to avoid live feed costs

---

## Data Depth & Historical Coverage

### Stock Data Depth

#### Real-Time (Live Feed)
- **Quote Level:** Level 1 (top of book)
- **Included:** Bid, ask, mid, last prices with volumes
- **Not Available:** Market depth, order book, L2/L3 data
- **Granularity:** Individual ticks

#### Intraday Historical
- **Resolutions:** 1-minute through 4-hour bars
- **Coverage:** All U.S.-traded stocks and ETFs
- **Depth:** Years of intraday history available
- **Granularity:** OHLCV + timestamp

#### Daily Historical
- **Coverage:** Decades of daily OHLCV data
- **Data Points:** Open, High, Low, Close, Volume
- **Adjustment:** Corporate actions adjusted
- **Availability:** Back to inception for actively traded securities

### Options Data Depth

#### Real-Time (Live Feed)
- **Source:** OPRA consolidated feed
- **Update Frequency:** Multiple times per second
- **Available Data:** Last price, bid, ask, implied volatility, Greeks (dependent on feed)
- **Limitation:** L2/L3 market depth NOT available

#### Historical (EOD Only)
- **Coverage:** 2010 - Present
- **Available Data:** EOD quotes for all expiring options
- **Granularity:** End-of-day snapshots
- **No Intraday History:** Hourly/minute-level option data unavailable
- **Limitation:** Futures options excluded

### Data NOT Available

- **Market Depth:** Level 2/Level 3 order book data
- **Intraday Options:** Minute-level option history
- **Futures Data:** Commodity and index futures
- **Crypto:** Cryptocurrencies not supported
- **Forex:** Foreign exchange data not offered
- **Financial Statements:** Balance sheets, income statements, cash flows
- **Advanced Fundamentals:** P/E ratios, dividend yields, valuation metrics
- **Analyst Revisions:** Estimate changes, target price changes, rating changes
- **Sentiment Analysis:** Social sentiment, alternative data sources
- **Dividend Data:** Dividend adjustments not supported (though split-adjusted data available)

---

## Pricing Plans & Rate Limits

### Plan Comparison

| Feature | Free | Starter | Trader | Quant | Prime |
|---|---|---|---|---|---|
| **Monthly Cost** | $0 | $12 | $30 | $125 | $250 |
| **Credits/Day** | 100 | 10,000 | 100,000 | Unlimited | Unlimited |
| **Credits/Minute** | N/A | N/A | N/A | 10,000 | 100,000 |
| **Data Feed** | Delayed | Configurable | Configurable | Configurable | Configurable |
| **Historical Data** | Limited | Full | Full | Full | Full |
| **Option Chains** | Yes | Yes | Yes | Yes | Yes |
| **Intraday Bars** | No | Yes | Yes | Yes | Yes |
| **Earnings Data** | AAPL only | Yes | Yes | Yes | Yes |
| **Economic Indicators** | No | Yes | Yes | Yes | Yes |
| **Trial Period** | N/A | 30 days | 30 days | 30 days | 30 days |

### Rate Limiting Rules

**Concurrent Requests Limit (All Plans):**
- Maximum 50 concurrent API requests at any given time
- Enforce client-side queuing to respect this limit

**Daily Credit Limits:**
- Free: 100 credits/day
- Starter: 10,000 credits/day
- Trader: 100,000 credits/day

**Per-Minute Limits:**
- Quant: 10,000 credits/minute (no daily cap)
- Prime: 100,000 credits/minute (no daily cap)

**Reset Schedule:**
- Daily limits reset at 9:30 AM Eastern Time (NYSE opening bell)
- Per-minute limits reset every 60 seconds

**Custom Plans:**
- MarketData can design custom plans for >100,000 requests/minute
- Contact sales for enterprise/high-volume requirements

### Credit Consumption

- **Single Quote Request:** ~1 credit
- **Candles Request:** Varies by date range (typically 1-10 credits)
- **Bulk Quotes:** ~0.5-1 credit per symbol
- **Feed Type Impact:** Delayed < Cached < Live (in credit cost)

**Optimization Tips:**
- Use bulk endpoints to reduce per-symbol overhead
- Leverage cached feed for non-time-sensitive data
- Implement client-side caching to avoid redundant API calls
- Batch multiple symbols in single requests when possible

---

## Response Formats

### JSON Format (Default)

**Example Stock Quote Response:**
```json
{
  "status": "ok",
  "results": [
    {
      "symbol": "AAPL",
      "last": 150.25,
      "bid": 150.20,
      "ask": 150.30,
      "askSize": 1000,
      "bidSize": 800,
      "mid": 150.25,
      "updated": "2026-04-04T16:00:00Z"
    }
  ]
}
```

**Example Candles Response:**
```json
{
  "status": "ok",
  "results": [
    {
      "o": 150.00,
      "h": 151.50,
      "l": 149.75,
      "c": 150.25,
      "v": 2500000,
      "t": "2026-04-04T16:00:00Z"
    }
  ]
}
```

### CSV Format

Add `format=csv` to any request to receive comma-separated values suitable for spreadsheet import.

**Advantages:**
- Direct import to Excel, Google Sheets
- No JSON parsing required
- Suitable for bulk historical data exports

**Example:**
```
GET /v1/stocks/candles/1d/AAPL?format=csv&from=2024-01-01&to=2024-12-31
```

### Universal Parameters

All endpoints support:

| Parameter | Type | Description |
|---|---|---|
| `format` | string | Response format: `json` (default) or `csv` |
| `feed` | string | Data feed: `live`, `cached`, `delayed` (paid plans only) |
| `limit` | integer | Max results to return |
| `offset` | integer | Pagination offset for results |

---

## Implementation Considerations

### Connection Strategy

#### 1. Initial Data Load (Historical Backfill)
- Use **cached feed** with bulk endpoints
- Fetch date ranges in chunks (e.g., 1 month at a time)
- Minimize concurrent requests to respect 50-request limit
- Store locally to avoid re-fetching

**Example Flow:**
```
1. Fetch OHLC data for past 1 year: /v1/stocks/candles/1d/{symbol}?from=2025-04&to=2026-04
2. Store in local database
3. Set up incremental daily updates
```

#### 2. Real-Time Monitoring (Active Trading)
- Use **live feed** for actively monitored positions
- Implement WebSocket subscriptions (if available) or polling with short intervals
- Cache frequently-requested symbols client-side
- Use bulk quote endpoint for multiple symbols

**Example Flow:**
```
1. Every 5 seconds: GET /v1/stocks/bulkquotes?symbols=AAPL,MSFT,GOOGL&feed=live
2. Update local cache
3. Trigger alerts if price crosses thresholds
```

#### 3. End-of-Day Reconciliation
- Use **delayed feed** if cost is concern
- Batch requests for all symbols at once
- Can wait until market close for complete daily data
- Perfect for portfolio tracking and performance analysis

### Error Handling

**Common Responses:**
- 200 OK: Successful request
- 400 Bad Request: Invalid parameters
- 401 Unauthorized: Invalid/missing API token
- 429 Too Many Requests: Rate limit exceeded
- 500 Server Error: API outage

**Retry Strategy:**
- Implement exponential backoff (1s, 2s, 4s, 8s max)
- Respect rate limits to avoid 429 errors
- Cache responses to reduce duplicate requests

### Data Quality Considerations

1. **Corporate Actions:** Stock data is adjusted for splits and dividends
2. **Symbol Validity:** Verify symbols exist before querying (AAPL works without auth)
3. **Market Hours:** Intraday data updates during market hours only (9:30 AM - 4:00 PM ET)
4. **Options Expiration:** Filter by expiration date in chain requests
5. **Timezone:** All timestamps in UTC; convert for market-hour logic

### Concurrency Best Practices

- Maintain queue of API requests
- Process max 50 concurrent requests
- Monitor rate limit usage against daily/minute cap
- Implement circuit breaker for quota exhaustion
- Log all API failures for audit trail

### Testing & Development

#### Free Testing Resources

- **Free AAPL Ticker:** Available without authentication for stock quotes and data
  ```bash
  curl -X GET "https://api.marketdata.app/v1/stocks/quotes/AAPL/"
  ```

- **Free Trial Symbols:** Test the API with these symbols before authentication:
  - **Stocks:** AAPL
  - **Options:** AAPL271217C00250000 (AAPL call option example)
  - **Mutual Funds:** VFINX

- **30-Day Trial:** Full access to test all paid plan features
  - 10,000-50,000 daily API calls depending on plan tier
  - Test all data feeds (live, cached, delayed)
  - Full access to earnings and fundamental data

#### Interactive Testing

- **Swagger UI:** Interactive API documentation and testing at https://api.marketdata.app/#/
  - Try API calls directly in browser
  - View response schemas
  - Test parameters before coding

- **Postman Collection:** Pre-built API requests for rapid testing
  - [Market Data API - Postman Collection](https://www.postman.com/marketdataapp/market-data/documentation/t8jjlx8/market-data-api-v1)
  - Import for quick testing of all endpoints
  - Pre-configured authentication

#### Development Best Practices

```bash
# Test with free AAPL quote first
curl -X GET "https://api.marketdata.app/v1/stocks/quotes/AAPL/"

# Test historical data (no auth needed)
curl -X GET "https://api.marketdata.app/v1/stocks/candles/1d/AAPL/?from=2025-01-01&to=2025-12-31"

# Test with your token after getting trial access
curl -X GET "https://api.marketdata.app/v1/stocks/quotes/MSFT/?feed=live" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Rate Limit Testing

- Free Plan: Monitor 100 credits/day
- Use curl with verbose flag to see rate limit headers:
  ```bash
  curl -X GET "https://api.marketdata.app/v1/stocks/quotes/AAPL/" -v
  ```

---

## Quick Reference: Common API Calls

### 1. Get Latest Stock Quote (Free, AAPL Only)
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/quotes/AAPL/"
```

Response:
```json
{
  "s": "ok",
  "ask": 150.30,
  "bid": 150.20,
  "last": 150.25,
  "mid": 150.25,
  "updated": "2026-04-04T16:00:00Z"
}
```

### 2. Get Real-Time Stock Quote (Paid, Live Feed)
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/quotes/MSFT/?feed=live" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Get 1-Year Daily Candles (Historical)
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/candles/1d/AAPL/?from=2025-04-04&to=2026-04-04" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "s": "ok",
  "o": [221.03, 218.55, 220],
  "h": [222.49, 221.5, 220.94],
  "l": [217.19, 217.1402, 218.83],
  "c": [217.68, 221.03, 219.89],
  "v": [33463820, 24018876, 20730608],
  "t": [1569297600, 1569384000, 1569470400]
}
```

### 4. Get Intraday 15-minute Bars (Last 50 Candles)
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/candles/15m/AAPL/?countback=50" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 5. Get Multiple Stock Quotes (Bulk, Cost-Effective)
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/bulkquotes?symbols=AAPL,MSFT,GOOGL&feed=cached" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 6. Get Complete Option Chain
```bash
curl -X GET "https://api.marketdata.app/v1/options/chain/AAPL/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 7. Get Specific Option Quote (OCC Format)
```bash
curl -X GET "https://api.marketdata.app/v1/options/quotes/AAPL271217C00250000/?feed=live" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "s": "ok",
  "bid": 2.45,
  "ask": 2.50,
  "last": 2.48,
  "delta": 0.65,
  "iv": 0.35,
  "volume": 15230
}
```

### 8. Get Call Options for Specific Expiration
```bash
curl -X GET "https://api.marketdata.app/v1/options/chain/MSFT/?expiration=2026-05-15&type=call" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 9. Get Historical Earnings Data (Starter+)
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/earnings/AAPL?from=2024-01-01&to=2026-04-04" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 10. Get Last 4 Earnings Reports (Starter+)
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/earnings/MSFT?countback=4" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 11. Export Daily Data as CSV
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/candles/1d/AAPL/?from=2025-01-01&to=2026-04-04&format=csv" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 12. Get Data with Cached Feed (Lower Cost)
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/quotes/AAPL/?feed=cached" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 13. Get Recent News for a Stock
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/news/AAPL/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "s": "ok",
  "headline": ["Apple Q2 Earnings Beat Expectations", "Apple Announces New Features"],
  "content": ["Apple reported record quarterly earnings...", "In a surprise announcement..."],
  "source": ["reuters.com", "bloomberg.com"],
  "publicationDate": ["2026-04-03T15:30:00Z", "2026-04-02T10:15:00Z"]
}
```

### 14. Get News Within Date Range
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/news/MSFT/?from=2026-03-01&to=2026-04-04" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 15. Get Last 10 News Articles
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/news/GOOGL/?countback=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 16. Get All Available Earnings Reports
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/earnings/AAPL/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 17. Get Last 4 Earnings Reports (Most Recent)
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/earnings/MSFT/?countback=4" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "s": "ok",
  "symbol": "MSFT",
  "fiscalYear": 2026,
  "fiscalQuarter": 2,
  "reportedEPS": 2.95,
  "estimatedEPS": 2.92,
  "surpriseEPS": 0.03,
  "surpriseEPSpct": 1.03,
  "reportTime": "after market close",
  "reportDate": "2026-04-23T16:30:00Z"
}
```

### 18. Get Earnings Reports Within Date Range
```bash
curl -X GET "https://api.marketdata.app/v1/stocks/earnings/GOOGL/?from=2024-01-01&to=2026-04-04" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## SDKs & Language Integration

### Go SDK

MarketData.app provides a Go SDK to simplify API integration:

```go
package main

import (
	"fmt"
	md "github.com/MarketData-App/marketdata-go"
)

func main() {
	// Initialize client with token
	client := md.New("YOUR_TOKEN")
	
	// Get stock quote
	quote, err := client.GetQuote("AAPL")
	if err != nil {
		panic(err)
	}
	
	fmt.Printf("AAPL: Bid=$%.2f, Ask=$%.2f\n", quote.Bid, quote.Ask)
	
	// Get historical candles
	candles, err := client.GetCandles("AAPL", "1d", nil)
	if err != nil {
		panic(err)
	}
	
	for _, c := range candles {
		fmt.Printf("Date: %s, Close: $%.2f\n", c.Timestamp, c.Close)
	}
}
```

### Python Integration Example

```python
import requests
from datetime import datetime, timedelta

class MarketDataAPI:
    def __init__(self, token):
        self.base_url = "https://api.marketdata.app/v1"
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def get_quote(self, symbol, feed="live"):
        """Fetch real-time stock quote"""
        url = f"{self.base_url}/stocks/quotes/{symbol}/"
        params = {"feed": feed}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
    
    def get_candles(self, symbol, resolution, days=365):
        """Fetch historical candles"""
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=days)
        
        url = f"{self.base_url}/stocks/candles/{resolution}/{symbol}/"
        params = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat()
        }
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
    
    def get_bulk_quotes(self, symbols, feed="cached"):
        """Fetch multiple quotes at once"""
        url = f"{self.base_url}/stocks/bulkquotes"
        params = {
            "symbols": ",".join(symbols),
            "feed": feed
        }
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

# Usage
api = MarketDataAPI("YOUR_TOKEN")

# Get quote
quote = api.get_quote("AAPL")
print(f"AAPL: ${quote['results'][0]['last']}")

# Get 1-year history
candles = api.get_candles("MSFT", "1d", days=365)
print(f"Fetched {len(candles['results'])} daily candles")

# Get multiple quotes
bulk = api.get_bulk_quotes(["AAPL", "MSFT", "GOOGL"])
for result in bulk['results']:
    print(f"{result['symbol']}: ${result['last']}")
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

class MarketDataAPI {
  constructor(token) {
    this.client = axios.create({
      baseURL: 'https://api.marketdata.app/v1',
      headers: { Authorization: `Bearer ${token}` }
    });
  }

  async getQuote(symbol, feed = 'live') {
    const response = await this.client.get(`/stocks/quotes/${symbol}/`, {
      params: { feed }
    });
    return response.data;
  }

  async getCandles(symbol, resolution, from, to) {
    const response = await this.client.get(
      `/stocks/candles/${resolution}/${symbol}/`,
      { params: { from, to } }
    );
    return response.data;
  }

  async getBulkQuotes(symbols, feed = 'cached') {
    const response = await this.client.get('/stocks/bulkquotes', {
      params: { symbols: symbols.join(','), feed }
    });
    return response.data;
  }

  async getOptionChain(symbol) {
    const response = await this.client.get(`/options/chain/${symbol}/`);
    return response.data;
  }
}

// Usage
const api = new MarketDataAPI('YOUR_TOKEN');

(async () => {
  // Get quote
  const quote = await api.getQuote('AAPL');
  console.log(`AAPL: $${quote.results[0].last}`);

  // Get candles
  const candles = await api.getCandles('MSFT', '1d', '2025-01-01', '2026-04-04');
  console.log(`Fetched ${candles.results.length} candles`);

  // Get bulk quotes
  const bulk = await api.getBulkQuotes(['AAPL', 'MSFT', 'GOOGL']);
  bulk.results.forEach(r => {
    console.log(`${r.symbol}: $${r.last}`);
  });
})();
```

---

## References & Additional Resources

- [MarketData.app Official Docs](https://www.marketdata.app/docs/)
- [API Reference](https://www.marketdata.app/docs/api/)
- [Rate Limiting Guide](https://www.marketdata.app/docs/api/rate-limiting)
- [Data Plans Documentation](https://www.marketdata.app/docs/account/plans/)
- [Plan Limits Details](https://www.marketdata.app/docs/account/plan-limits)
- [Universal Parameters](https://www.marketdata.app/docs/api/category/universal-parameters)
- [Data Feed Types](https://www.marketdata.app/docs/api/universal-parameters/feed)
- [GitHub Documentation](https://github.com/MarketData-App/documentation)
