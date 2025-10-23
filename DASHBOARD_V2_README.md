# Market Maker Pro Dashboard V2

## Overview

The new multi-page dashboard provides comprehensive analytics and monitoring for your USDHL/USDC market making bot on Hyperliquid.

## Features

### 📊 **Overview Page**
- **System Health Banner** - Real-time bot status with error tracking
- **Key Metrics**:
  - Realized P&L (net after fees)
  - Unrealized P&L (mark-to-market)
  - Total Volume & Trade Count
  - ROI Percentage
- **Cumulative Profit Chart** - 24-hour profit tracking
- **Position & Balance Display** - Current inventory with gauge chart
- **Recent Trades Feed** - Last 10 trades with side indicators

### 📈 **Trading Page**
- **Live Market Data**:
  - Best Bid/Ask with orderbook depth
  - Current Spread (bps and percentage)
  - Real-time price updates
- **Spread Tracking Chart** - 24-hour spread history with min/max/avg
- **Market Volatility Metrics**:
  - 1-hour volatility calculation
  - Price change tracking
  - High/Low prices
- **Open Positions Table** - FIFO queue with:
  - Order sequence
  - Cost basis per position
  - Minimum profitable sell price
  - Partial fill status

### 💰 **Performance Page**
- **Advanced Metrics**:
  - **Profit Factor** - Gross profit / Gross loss ratio
  - **Win Rate** - Percentage of profitable trades
  - **Total Fees** - Exchange fees paid
  - **Average Profit per Trade**
- **P&L Breakdown** - Switchable views:
  - Daily performance
  - Weekly performance
  - Monthly performance
- **Cumulative Profit Chart** - All-time performance
- **Trade Distribution** - Win/Loss pie chart

### 🛡️ **Risk Management Page**
- **Risk Metrics**:
  - **Inventory Risk** - Position as % of max position
  - **Total Exposure** - Capital at risk
  - **Max Position** - Highest inventory level
  - **Unrealized P&L** - Current mark-to-market
- **Inventory Risk Heatmap** - Color-coded risk levels:
  - 🟢 Safe (0-40%)
  - 🔵 Moderate (40-70%)
  - 🟡 High (70-90%)
  - 🔴 Critical (90-100%)
- **Unrealized P&L Chart** - Mark-to-market over time
- **Position History** - Inventory levels tracking

## Accessing the Dashboard

### Original Dashboard
```
http://localhost/
```

### New Multi-Page Dashboard
```
http://localhost/v2
```

## API Endpoints

### Market Data
- `GET /api/market/current` - Current market state (bid, ask, spread, depth)
- `GET /api/market/spread_history` - 24-hour spread history
- `GET /api/market/volatility` - Volatility metrics (1-hour window)

### Performance
- `GET /api/performance/unrealized_pnl` - Unrealized P&L calculation
- `GET /api/performance/metrics` - Profit factor, ROI, win rate, fees
- `GET /api/performance/pnl_breakdown` - Daily/weekly/monthly P&L

### System
- `GET /api/system/health` - Bot health status and recent events

### Existing Endpoints
- `GET /api/stats` - Current bot statistics
- `GET /api/trades/recent` - Recent trades
- `GET /api/trades/history` - Trade history for charts
- `GET /api/position/history` - Position snapshots
- `GET /api/positions/open` - Open positions (FIFO queue)

## Database Schema

### New Tables

#### `market_snapshots`
Tracks orderbook state for spread and volatility analysis:
- `timestamp` - Snapshot time (milliseconds)
- `mid_price` - Mid-market price
- `best_bid` / `best_ask` - Top of book
- `spread_bps` - Spread in basis points
- `bid_depth_5` / `ask_depth_5` - Top 5 levels depth

#### `order_events`
Logs order lifecycle for tracking:
- `timestamp` - Event time
- `order_id` - Order identifier
- `event_type` - placed, cancelled, filled, modified
- `side` - buy or sell
- `price` / `amount` - Order details
- `reason` - Event reason/context

#### `daily_metrics`
Aggregated daily performance:
- `date` - Trading date
- `total_trades` / `total_volume`
- `realized_profit` / `fees_paid`
- `avg_spread_bps`
- `max_position` / `min_position`

#### `system_events`
System health monitoring:
- `timestamp` - Event time
- `event_type` - error, warning, info
- `severity` - error, warning, info
- `message` - Event description
- `details` - Additional context

## Configuration

The bot now tracks additional data automatically:
- Market snapshots every 3 seconds (configurable via `LOOP_INTERVAL`)
- Orderbook depth (top 5 levels)
- Spread in basis points
- System events and errors

## Performance Calculations

### Profit Factor
```
Profit Factor = Gross Profit / Gross Loss
```
- Values > 2.0 are excellent
- Values > 1.5 are good
- Values < 1.0 indicate net losses

### ROI (Return on Investment)
```
ROI % = (Total Profit / Initial Capital) × 100
```
Based on first 10 buy trades as initial capital estimate.

### Unrealized P&L
```
Cost Basis = Average Buy Price × Position
Current Value = Current Market Price × (1 - Fee) × Position
Unrealized P&L = Current Value - Cost Basis
```

### Volatility
Standard deviation of price returns over 1-hour window:
```
Returns = [(Price[i] - Price[i-1]) / Price[i-1]]
Volatility = √(Σ(Returns²) / N) × 100
```

## Navigation

The dashboard uses client-side routing with 4 main pages:
1. **Overview** - Quick snapshot of bot performance
2. **Trading** - Market microstructure and orderbook
3. **Performance** - Detailed profit analysis
4. **Risk** - Position and exposure management

Click the sidebar navigation items to switch between pages. Data updates every 5 seconds automatically.

## System Health

The health banner shows bot status:
- 🟢 **Healthy** - All systems operational
- 🟡 **Warning** - Some issues detected (>5 errors/hour or no trades for 10min)
- 🔴 **Error** - Critical issues (bot not responding for >60s)

## Browser Compatibility

Tested on:
- Chrome/Edge (recommended)
- Firefox
- Safari

Requires JavaScript enabled and supports modern ES6+ features.

## Troubleshooting

### Dashboard not loading
1. Check that `dashboard_api.py` is running
2. Verify Flask is serving on the correct port
3. Check browser console for errors

### No data showing
1. Ensure `main.py` bot is running
2. Check that database file exists and is accessible
3. Verify API endpoints return data (visit `/api/stats` directly)

### Charts not updating
1. Check browser console for JavaScript errors
2. Verify Chart.js library is loading
3. Clear browser cache and reload

## Future Enhancements

Potential additions:
- Real-time WebSocket updates
- Alert configuration UI
- Strategy parameter tuning interface
- Historical backtesting visualization
- Multi-pair support
- Export data to CSV/JSON
- Mobile-responsive design improvements

## Support

For issues or questions, check:
1. Browser console for errors
2. Flask logs for API errors
3. Database integrity with SQLite browser
