# Manual Testing Checklist - Realtime Watchlist & Charts

This checklist covers manual testing scenarios for the realtime watchlist and current day candle features.

## Prerequisites

- [ ] Backend server running with valid `MARKETDATA_API_TOKEN`
- [ ] Frontend dev server running (`npm run dev`)
- [ ] Test user account created and logged in
- [ ] At least one watchlist with 5-10 symbols
- [ ] System clock set to a time during market hours (for initial testing)

## Market Hours Testing

### During Market Hours (Mon-Fri 9:30 AM - 4:00 PM ET)

- [ ] **Polling Active**: Verify browser devtools Network tab shows requests every ~30s
- [ ] **Green Dots**: All symbol rows show green indicator dots
- [ ] **Price Updates**: Watch prices change over time (wait 1-2 minutes)
- [ ] **Current Day Candle**: Load daily chart, verify extra candle appears for current day
- [ ] **Chart Updates**: Current day candle updates every ~30s

### After Market Close (4:00 PM ET or weekends)

- [ ] **Polling Stops**: Network tab shows no requests after market close
- [ ] **Gray Dots**: All symbol rows show gray indicator dots
- [ ] **EOD Data**: Prices show yesterday's closing prices
- [ ] **No Current Day Candle**: Daily chart shows only historical candles
- [ ] **Polling Resumes**: At 9:30 AM ET next market day, polling resumes automatically

## Watchlist Functionality

### Basic Display

- [ ] **Symbol Rows**: Each symbol shows ticker, last price, change, change %
- [ ] **Source Indicators**: Green dot (realtime) or gray dot (EOD) visible
- [ ] **Positive Changes**: Green text with + prefix
- [ ] **Negative Changes**: Red text (no + prefix)
- [ ] **Loading State**: Skeleton rows show while fetching

### Auto-Refresh

- [ ] **Initial Load**: Quotes appear when watchlist expands
- [ ] **30-Second Updates**: Prices update automatically (watch for ~1 minute)
- [ ] **Multiple Watchlists**: Expanding multiple watchlists polls all of them
- [ ] **Collapsed Groups**: Collapsed watchlists don't fetch quotes
- [ ] **Market Hours Check**: Polling stops when market closes

### Manual Refresh

- [ ] **Refresh Button**: Click ↻ button, quotes update immediately
- [ ] **Button Animation**: Spinning icon during refresh
- [ ] **Retry on Error**: Click retry button after network error

### Empty/Error States

- [ ] **Empty Watchlist**: Shows "No symbols yet" message
- [ ] **Network Error**: Shows "Prices unavailable — ↻ retry" message
- [ ] **Add Symbol**: New symbol appears after adding
- [ ] **Remove Symbol**: Symbol disappears after removing

## Chart Functionality

### Current Day Candle Display

- [ ] **Daily Resolution Only**: Current day candle only shows on "D" timeframe
- [ ] **Intraday Resolutions**: No current day candle on 5m, 15m, 1h
- [ ] **Market Hours Check**: Only appears during market hours
- [ ] **Candle Position**: Current day candle is rightmost on chart
- [ ] **Candle Color**: Green if close > open, red if close < open

### Current Day Candle Updates

- [ ] **Initial Load**: Current day candle appears when chart loads
- [ ] **30-Second Updates**: Candle's close price updates every ~30s
- [ ] **OHL Stability**: Open, high, low remain stable (from intraday)
- [ ] **Close Updates**: Close price tracks latest quote
- [ ] **After Close**: Candle disappears when market closes

### Chart Interactions

- [ ] **Resolution Switch**: Switch to/from daily, current day candle appears/disappears
- [ ] **Symbol Change**: Select different symbol, current day candle updates
- [ ] **Time Scale**: Chart auto-scales to show current day candle
- [ ] **Crosshair**: Hovering shows current day candle data

### Chart Data Accuracy

- [ ] **OHL Match**: Open/high/low match intraday 1h bars
- [ ] **Close Match**: Close matches latest realtime quote
- [ ] **Volume**: Volume matches intraday volume
- [ ] **Timestamp**: Time matches current trading day

## Performance Testing

### API Performance

- [ ] **Response Time**: `/quotes` endpoint responds in <500ms
- [ ] **Cache Hit Rate**: Most requests hit cache (check logs)
- [ ] **Batch Efficiency**: Single batch request for multiple symbols
- [ ] **Rate Limits**: Stays within MarketData.app rate limits

### Browser Performance

- [ ] **Memory Usage**: Memory stable over time (no leaks)
- [ ] **CPU Usage**: CPU usage minimal between polls
- [ ] **UI Responsiveness**: No lag during quote updates
- [ ] **Network Requests**: Only one request per 30s per expanded watchlist

### Database Performance

- [ ] **Query Speed**: realtime_quotes queries fast (<100ms)
- [ ] **Index Usage**: Explain analyze shows index usage
- [ ] **Delete Pattern**: DELETE+INSERT pattern efficient
- [ ] **No Deadlocks**: No database lock issues

## Edge Cases

### Large Watchlists

- [ ] **100+ Symbols**: Watchlist with 100+ symbols works smoothly
- [ ] **Batch Splitting**: Multiple API calls for >50 symbols
- [ ] **UI Performance**: No lag with many symbol rows

### Duplicate Symbols

- [ ] **Same Symbol Across Lists**: Same symbol in multiple watchlists
- [ ] **Deduplication**: Worker fetches each unique symbol once
- [ ] **All Lists Update**: All watchlists update simultaneously

### Missing Data

- [ ] **No Intraday Data**: Symbol with no intraday candles
- [ ] **No Realtime Quote**: Symbol with no realtime quote
- [ ] **Invalid Symbol**: Symbol not in MarketData.app
- [ ] **Partial Data**: Some symbols have data, others don't

### Time Zone Issues

- [ ] **DST Transition**: Polling works correctly during DST transitions
- [ ] **Midnight ET**: Midnight Eastern time handled correctly
- [ ] **Weekend Boundaries**: 9:30 PM Friday → Monday 9:30 AM transition

### Network Issues

- [ ] **Slow Network**: Slow 3G network, polls complete successfully
- [ ] **Timeout**: Request timeout, next poll succeeds
- [ ] **Intermittent Failure**: Network drops occasionally, auto-recovers
- [ ] **Offline Mode**: No network, shows error toast

## Integration Testing

### Scheduler Integration

- [ ] **Job Registered**: `quote_poller` job in `/api/schedule/jobs`
- [ ] **Job Enabled**: Job status is "enabled"
- [ ] **Job Executes**: Logs show "Polled X quotes" every 30s
- [ ] **Job Respects Hours**: Job skips execution outside market hours

### Cache Integration

- [ ] **Cache Hit**: Second request for same symbols uses cache
- [ ] **Cache Miss**: First request or expired cache hits database
- [ ] **Cache Expiration**: 30-second TTL works correctly
- [ ] **Thread Safety**: No race conditions with concurrent requests

### Database Integration

- [ ] **Realtime Quotes Table**: Data stored correctly
- [ ] **Timestamp Accuracy**: Timestamps set to current time
- [ ] **Today's Data**: DELETE removes old today's data before INSERT
- [ ] **Query Performance**: Fast lookups by symbol

## Regression Testing

### Existing Features Still Work

- [ ] **Manual Watchlist Creation**: Create watchlist still works
- [ ] **Add/Remove Symbols**: Add/remove functionality unchanged
- [ ] **Categories**: Category grouping still works
- [ ] **Scanner Integration**: Auto-generated watchlists still work
- [ ] **Historical Charts**: Intraday/historical charts unchanged

### No Breaking Changes

- [ ] **API Compatibility**: Existing API endpoints unchanged
- [ ] **Database Schema**: No breaking schema changes
- [ ] **Frontend Routes**: No changes to existing routes
- [ ] **User Settings**: User preferences unaffected

## Notes

- **Testing Time**: Best tested during actual market hours for realistic behavior
- **Mock Data**: Can use mock MarketData.app responses for off-hours testing
- **Browser DevTools**: Use Network tab to verify polling behavior
- **Logs**: Check backend logs for worker activity and errors
- **Manual Clock Temporarity**: Can adjust system clock temporarily to test market hours boundaries

## Sign-Off

**Tester**: _________________ **Date**: ___________

**Environment**: ☐ Development ☐ Staging ☐ Production

**Browser**: ☐ Chrome ☐ Firefox ☐ Safari ☐ Edge

**Overall Status**: ☐ Pass ☐ Fail ☐ Partial Pass

**Notes**: _____________________________________________________
