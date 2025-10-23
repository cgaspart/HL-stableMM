# Migration Guide - Dashboard V2

## Quick Start

### 1. Database Migration
The new tables will be created automatically when you restart `main.py`. The bot will initialize the new schema on startup.

**No manual database migration needed!** The `init_database()` function creates all new tables if they don't exist.

### 2. Start the Bot
```bash
python main.py
```

The bot will now:
- ✅ Create new database tables automatically
- ✅ Track market snapshots every 3 seconds
- ✅ Log orderbook depth and spread
- ✅ Record system events

### 3. Start the Dashboard API
```bash
python dashboard_api.py
```

Or if using Docker:
```bash
docker-compose up
```

### 4. Access the New Dashboard
Open your browser to:
```
http://localhost/v2
```

The original dashboard is still available at:
```
http://localhost/
```

## What's New

### Backend Changes

#### `main.py` Enhancements
- **New function**: `save_market_snapshot()` - Captures orderbook state
- **New function**: `log_order_event()` - Tracks order lifecycle
- **New function**: `log_system_event()` - Records system health
- **Enhanced main loop**: Now calculates and saves orderbook depth

#### `dashboard_api.py` New Endpoints
- `/api/market/current` - Live market data
- `/api/market/spread_history` - Spread tracking
- `/api/market/volatility` - Volatility metrics
- `/api/performance/unrealized_pnl` - Mark-to-market P&L
- `/api/performance/metrics` - Profit factor, ROI, win rate
- `/api/performance/pnl_breakdown` - Daily/weekly/monthly breakdown
- `/api/system/health` - Bot health monitoring

### Frontend Changes

#### New Files
- `templates/dashboard_v2.html` - Multi-page dashboard
- `static/css/dashboard_v2.css` - Modern styling
- `static/js/dashboard_v2.js` - Enhanced functionality

#### Features
- 4-page navigation (Overview, Trading, Performance, Risk)
- Real-time system health monitoring
- Live orderbook visualization
- Spread tracking over time
- Market volatility indicators
- Profit factor calculation
- ROI percentage tracking
- Daily/Weekly/Monthly P&L breakdown
- Inventory risk heatmap
- Unrealized P&L tracking

## Data Collection

### What Gets Tracked Now

#### Market Snapshots (every 3 seconds)
- Mid price
- Best bid/ask
- Spread in basis points
- Orderbook depth (top 5 levels)

#### Order Events (when orders are placed/cancelled)
- Order ID
- Event type (placed, cancelled, filled)
- Side (buy/sell)
- Price and amount
- Reason/context

#### System Events (when issues occur)
- Timestamp
- Event type
- Severity level
- Message and details

### Storage Impact

Approximate database growth:
- **Market snapshots**: ~20 records/minute = ~28,800/day ≈ 5MB/day
- **Order events**: Varies by activity, typically 100-1000/day ≈ 0.1MB/day
- **System events**: Minimal, only on errors/warnings

**Recommendation**: Monitor database size and implement cleanup for old data if needed (e.g., keep only last 30 days of market snapshots).

## Testing the New Dashboard

### 1. Verify Data Collection
After running the bot for a few minutes, check if data is being collected:

```bash
sqlite3 market_maker.db "SELECT COUNT(*) FROM market_snapshots;"
```

Should return a number > 0.

### 2. Test API Endpoints
Visit these URLs in your browser:
- http://localhost/api/market/current
- http://localhost/api/performance/metrics
- http://localhost/api/system/health

All should return JSON data.

### 3. Check Dashboard Pages
Navigate through all 4 pages in the dashboard:
1. Overview - Should show key metrics and recent trades
2. Trading - Should display live market data and spread chart
3. Performance - Should show profit factor and P&L breakdown
4. Risk - Should display inventory risk and unrealized P&L

## Rollback Plan

If you need to revert to the old dashboard:

### Option 1: Use Original Dashboard
Simply visit `http://localhost/` instead of `/v2`

### Option 2: Remove New Code
The new code doesn't interfere with existing functionality. You can:
1. Keep using `main.py` (new tables are optional)
2. Use original dashboard at `/`
3. Ignore new API endpoints

### Option 3: Database Cleanup
If you want to remove new tables:
```sql
DROP TABLE IF EXISTS market_snapshots;
DROP TABLE IF EXISTS order_events;
DROP TABLE IF EXISTS daily_metrics;
DROP TABLE IF EXISTS system_events;
```

**Note**: This will delete all collected market data.

## Performance Considerations

### CPU Impact
- Minimal: ~1-2% additional CPU for data collection
- Market snapshots are lightweight (just storing numbers)

### Memory Impact
- Negligible: ~10-20MB additional memory usage
- Charts render client-side in browser

### Network Impact
- Dashboard polls every 5 seconds
- Each poll makes ~10 API calls
- Total: ~50KB/5s = ~10KB/s bandwidth

### Optimization Tips
1. **Reduce snapshot frequency**: Change `LOOP_INTERVAL` in main.py
2. **Limit chart data**: Modify API endpoints to return fewer records
3. **Increase dashboard update interval**: Change `5000` to `10000` in dashboard_v2.js

## Troubleshooting

### Issue: New tables not created
**Solution**: Restart `main.py` - tables are created on startup

### Issue: Dashboard shows no data
**Solution**: 
1. Check bot is running: `ps aux | grep main.py`
2. Verify API is accessible: `curl http://localhost/api/stats`
3. Check browser console for errors

### Issue: Charts not rendering
**Solution**:
1. Clear browser cache
2. Check Chart.js is loading (browser dev tools → Network tab)
3. Verify data is returned from API endpoints

### Issue: High database size
**Solution**: Implement data retention policy
```sql
-- Delete market snapshots older than 7 days
DELETE FROM market_snapshots 
WHERE timestamp < (strftime('%s', 'now') - 604800) * 1000;
```

## Best Practices

### 1. Monitor Database Size
```bash
# Check database size
ls -lh market_maker.db

# Check table sizes
sqlite3 market_maker.db "SELECT name, COUNT(*) FROM sqlite_master WHERE type='table' GROUP BY name;"
```

### 2. Regular Backups
```bash
# Backup database
cp market_maker.db market_maker_backup_$(date +%Y%m%d).db

# Or use SQLite backup
sqlite3 market_maker.db ".backup market_maker_backup.db"
```

### 3. Performance Monitoring
Watch for:
- API response times (should be < 100ms)
- Dashboard load time (should be < 2s)
- Database query performance

### 4. Data Retention
Consider implementing cleanup jobs:
```python
# Add to main.py or separate cleanup script
def cleanup_old_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Keep only last 30 days of market snapshots
    cutoff = int(time.time() * 1000) - (30 * 24 * 60 * 60 * 1000)
    cursor.execute('DELETE FROM market_snapshots WHERE timestamp < ?', (cutoff,))
    
    # Keep only last 90 days of system events
    cutoff = int(time.time() * 1000) - (90 * 24 * 60 * 60 * 1000)
    cursor.execute('DELETE FROM system_events WHERE timestamp < ?', (cutoff,))
    
    conn.commit()
    conn.close()
```

## Support & Feedback

The new dashboard is fully backward compatible. Your existing setup will continue to work, and you can switch between old and new dashboards at any time.

Enjoy your enhanced market making analytics! 🚀
