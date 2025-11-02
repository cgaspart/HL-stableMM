# Grid Trading Strategy

## Overview

The grid trading strategy implements independent buy/sell pairs for stablecoin market making. Unlike the inventory-based approach, each grid level operates independently with its own P&L tracking.

## Key Differences from Inventory Strategy

### Inventory-Based (main.py)
- Accumulates position → calculates average buy price
- Sells only when price > breakeven of entire position
- Profit locked until entire inventory is profitable
- Better for trending markets

### Grid Trading (main_grid.py)
- Each trade is independent
- Buy @ X → Sell @ X + profit target
- Locks in profit on each completed cycle
- Better for ranging/oscillating markets (like stablecoins)

## How It Works

### Grid Structure
```
Level 0: Buy @ 0.99750 → Sell @ 0.99850 (10 bps profit)
Level 1: Buy @ 0.99755 → Sell @ 0.99855 (10 bps profit)
Level 2: Buy @ 0.99760 → Sell @ 0.99860 (10 bps profit)
...
Level 9: Buy @ 0.99795 → Sell @ 0.99895 (10 bps profit)
```

### Execution Flow
1. **Initialization**: Grid centered around current mid-price (capped at 0.9999)
2. **Place Orders**: All buy orders placed (optionally sell orders too)
3. **Buy Fill**: When buy fills → immediately place paired sell order
4. **Sell Fill**: When sell fills → calculate profit → place new buy order at same level
5. **Rebalance**: If price moves >50 bps, recreate grid at new center

### Important Safety Features
- **Max Buy Price**: Never buys above 0.9999 (stablecoin peg protection)
- **No Duplicate Buys**: Won't place new buy until sell completes
- **Status Tracking**: Each level tracks its state (buy_placed → buy_filled → sell_placed → completed)

### Profit Calculation
```python
Buy Cost = buy_price × (1 + 0.0004)  # Include maker fee
Sell Revenue = sell_price × (1 - 0.0004)  # Deduct maker fee
Profit = (Sell Revenue - Buy Cost) × size
```

## Configuration

### Grid Parameters (config.py)

```python
# Grid structure
GRID_LEVELS = 10              # Number of grid levels
GRID_SIZE = 50                # USDHL per level
GRID_SPACING_BPS = 5          # 5 bps between levels
PROFIT_TARGET_BPS = 10        # 10 bps profit per cycle

# Risk management
MAX_GRID_POSITION = 500       # Max total inventory
GRID_REBALANCE_THRESHOLD_BPS = 50  # Rebalance at 50 bps move

# Execution
GRID_CHECK_INTERVAL = 2       # Grid order placement
GRID_MIN_ORDER_VALUE = 10.0   # Min $10 per order
GRID_PLACE_BOTH_SIDES = True   # Place both buy & sell initially
GRID_MAX_BUY_PRICE = 0.9999    # Never buy above this (stablecoin peg protection)
```

### Recommended Settings

**Conservative (Lower Risk)**
- GRID_LEVELS = 5
- GRID_SIZE = 30
- PROFIT_TARGET_BPS = 15
- GRID_REBALANCE_THRESHOLD_BPS = 30

**Balanced (Recommended)**
- GRID_LEVELS = 10
- GRID_SIZE = 50
- PROFIT_TARGET_BPS = 10
- GRID_REBALANCE_THRESHOLD_BPS = 50

**Aggressive (Higher Volume)**
- GRID_LEVELS = 20
- GRID_SIZE = 50
- PROFIT_TARGET_BPS = 8
- GRID_REBALANCE_THRESHOLD_BPS = 100

## Usage

### Start Grid Bot
```bash
./start_grid.sh
```

### Monitor Performance
The bot logs:
- Grid initialization and rebalancing
- Buy/sell fills with profit calculations
- Grid status (levels filled, completed cycles, total profit)

### Database Tracking
Grid orders are tracked in:
- `grid_orders`: Individual order pairs and their status
- `grid_state`: Grid configuration snapshots
- `trades`: All executed trades (shared with inventory strategy)

### Query Grid Performance
```sql
-- Total profit by grid
SELECT grid_id, SUM(profit) as total_profit, COUNT(*) as completed_cycles
FROM grid_orders 
WHERE status = 'completed'
GROUP BY grid_id;

-- Active grid levels
SELECT level_index, buy_price, sell_price, status
FROM grid_orders
WHERE grid_id = (SELECT grid_id FROM grid_state WHERE is_active = 1)
ORDER BY level_index;
```

## Advantages

1. **Independent P&L**: Each cycle profits independently
2. **Better for Tight Spreads**: Can profit on 5-10 bps moves
3. **No Averaging Risk**: Not locked into bad average price
4. **Predictable Profit**: Know exact profit per cycle
5. **Capital Efficient**: Don't wait for entire position to be profitable

## Risk Considerations

1. **Trending Markets**: Grid can accumulate position in strong trends
2. **Rebalancing Costs**: Frequent rebalancing = more cancelled orders
3. **Position Limits**: Must respect MAX_GRID_POSITION
4. **USDC Requirements**: Need enough USDC for all buy orders

## Monitoring

### Key Metrics
- **Completed Cycles**: Number of buy→sell pairs completed
- **Total Profit**: Sum of all completed cycle profits
- **Fill Rate**: % of grid levels that have filled
- **Current Position**: Total USDHL held across all levels

### Health Checks
- Grid should rebalance when price moves >50 bps
- Position should stay < MAX_GRID_POSITION
- All levels should have active orders
- Profit per cycle should be ~10 bps (after fees)

## Comparison: Your Historical Trades

### With Inventory Strategy (Actual)
- Total buys: ~336 USDHL @ avg 0.99809
- Total sells: ~336 USDHL @ avg 0.99909
- Net: ~-$0.48 loss (spread too tight, fees ate profit)

### With Grid Strategy (Estimated)
- Each 50 USDHL cycle @ 10 bps profit = $0.50 profit
- ~6-7 cycles possible = ~$3-3.50 profit
- Much better for oscillating stablecoin prices

## Switching Between Strategies

Both strategies can coexist:
- `main.py` - Inventory-based strategy
- `main_grid.py` - Grid trading strategy

Choose based on market conditions:
- **Trending**: Use inventory strategy (main.py)
- **Ranging**: Use grid strategy (main_grid.py)
- **Stablecoins**: Grid strategy usually better

## Troubleshooting

### Grid not placing orders
- Check USDC balance
- Verify GRID_MIN_ORDER_VALUE is met
- Check position < MAX_GRID_POSITION

### Too many rebalances
- Increase GRID_REBALANCE_THRESHOLD_BPS
- Widen GRID_SPACING_BPS

### Low profit per cycle
- Increase PROFIT_TARGET_BPS
- Check maker fees are correct (0.04%)
- Verify spread is wide enough

### Position accumulating
- Grid is trending - consider stopping
- Reduce GRID_LEVELS
- Increase GRID_SPACING_BPS
