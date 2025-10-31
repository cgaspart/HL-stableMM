# Hyperliquid Stablecoin Market Maker

Automated market making bot for USDHL/USDC on Hyperliquid with real-time dashboard.

![Dashboard](image.png)

## Features

- **Smart Market Making**: Inventory-aware pricing with dynamic spread adjustment
- **Incremental Selling**: Sells in tranches to maximize profit
- **Average-Down Protection**: Only buys below current average cost
- **Real-time Dashboard**: Flask-based web UI with performance metrics
- **Persistent Storage**: SQLite database for trade history and analytics
- **Docker Support**: Single-container deployment

## Quick Start

### 1. Setup Environment

```bash
cp .env.example .env
# Edit .env with your Hyperliquid credentials
```

### 2. Run with Docker

```bash
docker-compose up -d
```

### 3. Access Dashboard

```
http://localhost:5000
```

## Configuration

Edit `config.py` to adjust strategy parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ORDER_SIZE` | 50 | Base order size in USDHL |
| `MAX_POSITION` | 500 | Maximum inventory limit |
| `MIN_SPREAD_BPS` | 3 | Minimum spread to trade (0.03%) |
| `SELL_TRANCHES` | 4 | Number of sell levels |
| `ONLY_AVERAGE_DOWN` | True | Only buy below average cost |

## Architecture

```
config.py            → Centralized configuration and parameters
logger.py            → Logging utilities
database.py          → SQLite operations (trades, snapshots, events)
exchange.py          → Hyperliquid exchange wrapper
market_maker.py      → Core market making strategy logic
order_manager.py     → Order placement and lifecycle management
main.py              → Bot orchestration and main loop
dashboard_api.py     → Flask API + web server (optional)
market_maker.db      → SQLite database (trades, positions, metrics)
templates/           → Dashboard HTML (optional)
static/              → CSS/JS assets (optional)
```

## Module Overview

- **`config.py`**: All parameters in one place (market making, order sizing, strategy thresholds)
- **`logger.py`**: Timestamped logging utility
- **`database.py`**: All database operations (initialization, trade tracking, snapshots, events)
- **`exchange.py`**: `HyperliquidExchange` class wrapping CCXT operations
- **`market_maker.py`**: `MarketMaker` class with pricing, sizing, and inventory management logic
- **`order_manager.py`**: `OrderManager` class for order placement, cancellation, and requoting
- **`main.py`**: `StablecoinMarketMakerBot` orchestrator that ties everything together

## API Endpoints

- `GET /api/stats` - Current position and P&L
- `GET /api/trades/recent` - Latest 50 trades
- `GET /api/performance/stats` - Win rate, profit factor, ROI
- `GET /api/market/spread` - Spread analysis
- `GET /api/system/health` - Bot health status

## Database Schema

**trades**: Trade history with P&L tracking  
**position_snapshots**: Inventory over time  
**market_snapshots**: Spread and depth data  
**order_events**: Order lifecycle logs  

## Requirements

- Python 3.9+
- ccxt >= 4.0.0
- Flask >= 3.0.0
- Docker (optional)

## Manual Installation

```bash
pip install -r requirements.txt

# Run bot (includes all modular components)
python main.py

# Optional: Run dashboard in separate terminal
python dashboard_api.py
```

## Safety Features

- **Position Limits**: Enforced max inventory
- **Spread Validation**: Won't trade if spread too narrow
- **Fee Accounting**: Includes maker fees in cost basis
- **Order Management**: Smart requoting to minimize API calls
- **Database Persistence**: Recovers state on restart

## Extending the Bot

### Custom Strategies
1. Create new strategy class in `market_maker.py`
2. Switch strategies via config parameter
3. Test independently before deployment

## Monitoring

View logs:
```bash
docker-compose logs -f
```

Check health:
```bash
curl http://localhost:5000/api/system/health
```