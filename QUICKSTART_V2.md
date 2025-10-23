# 🚀 Quick Start - Dashboard V2

## 3 Simple Steps

### Step 1: Start the Bot
```bash
python main.py
```
✅ Creates new database tables automatically  
✅ Starts tracking market data  
✅ Begins market making  

### Step 2: Start the Dashboard
```bash
python dashboard_api.py
```
✅ Launches Flask API server  
✅ Serves dashboard on port 80  
✅ Exposes all analytics endpoints  

### Step 3: Open Your Browser
```
http://localhost/v2
```
✅ View the new multi-page dashboard  
✅ Explore 4 pages of analytics  
✅ Monitor your bot in real-time  

---

## 🎯 What You'll See

### Overview Page
- System health status
- Realized & Unrealized P&L
- Total volume and ROI
- Recent trades feed

### Trading Page
- Live orderbook (bid/ask/spread)
- Spread tracking chart
- Market volatility metrics
- Open positions table

### Performance Page
- Profit factor & win rate
- Total fees paid
- Daily/Weekly/Monthly P&L
- Trade distribution

### Risk Page
- Inventory risk heatmap
- Unrealized P&L tracking
- Position exposure
- Risk level indicators

---

## 🔧 Troubleshooting

### Dashboard not loading?
```bash
# Check if Flask is running
ps aux | grep dashboard_api.py

# Restart if needed
pkill -f dashboard_api.py
python dashboard_api.py
```

### No data showing?
```bash
# Check if bot is running
ps aux | grep main.py

# Check database exists
ls -lh market_maker.db

# Test API directly
curl http://localhost/api/stats
```

### Port already in use?
```bash
# Change port in dashboard_api.py
# Or kill existing process
lsof -ti:80 | xargs kill -9
```

---

## 📊 Key Features at a Glance

| Feature | Location | Description |
|---------|----------|-------------|
| **Live Orderbook** | Trading | Real-time bid/ask/spread |
| **Spread Tracking** | Trading | 24h spread history chart |
| **Volatility** | Trading | 1h market volatility |
| **Profit Factor** | Performance | Win/loss ratio |
| **ROI** | Overview | Return on investment |
| **P&L Breakdown** | Performance | Daily/weekly/monthly |
| **Inventory Risk** | Risk | Position heatmap |
| **Unrealized P&L** | Risk | Mark-to-market |
| **System Health** | Overview | Bot status monitoring |

---

## 💡 Pro Tips

1. **Bookmark the dashboard**: `http://localhost/v2`
2. **Keep it open**: Auto-refreshes every 5 seconds
3. **Check all pages**: Each has unique insights
4. **Monitor health banner**: Green = good, Red = issues
5. **Watch inventory risk**: Stay in green/blue zones

---

## 🎨 Navigation

Click sidebar items to switch pages:
- 📊 **Overview** - Quick snapshot
- 📈 **Trading** - Market data
- 💰 **Performance** - Profit analysis
- 🛡️ **Risk** - Position management

---

## 🔗 Useful Links

- **Original Dashboard**: `http://localhost/`
- **API Stats**: `http://localhost/api/stats`
- **Health Check**: `http://localhost/api/system/health`
- **Full Documentation**: See `DASHBOARD_V2_README.md`
- **Migration Guide**: See `MIGRATION_GUIDE.md`

---

## ⚡ Quick Commands

```bash
# Start everything
python main.py &
python dashboard_api.py &

# Stop everything
pkill -f main.py
pkill -f dashboard_api.py

# Check status
ps aux | grep python

# View logs
tail -f nohup.out

# Backup database
cp market_maker.db backup_$(date +%Y%m%d).db
```

---

## 🎉 You're Ready!

Your professional market maker dashboard is now running. Enjoy the enhanced analytics and happy trading! 🚀

**Questions?** Check the full documentation in `DASHBOARD_V2_README.md`
