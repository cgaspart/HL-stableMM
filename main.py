import ccxt
import time
import sqlite3
from datetime import datetime
import os

# Database configuration
DB_PATH = os.getenv('DB_PATH', 'market_maker.db')

def get_db_connection():
    """Get database connection with proper timeout and WAL mode"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    # Enable WAL mode for better concurrency
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')  # 30 second timeout
    return conn

# load data from env

exchange = ccxt.hyperliquid({
    'walletAddress': os.getenv('WALLET_ADDRESS'),
    'privateKey': os.getenv('PRIVATE_KEY'),
    'enableRateLimit': True,
    # Note: vaultAddress is for perps only, not spot trading
})

# Configuration
MAKER_FEE = 0.0004  # 0.04% maker fee for Hyperliquid spot
ORDER_SIZE = 50  # Base size in USDHL per order
MAX_POSITION = 500  # Maximum inventory in USDHL (increased for more volume)
LOOP_INTERVAL = 3  # seconds between iterations (faster updates for more volume)
TICK_SIZE = 0.00001  # Minimum price increment for USDHL/USDC
SKEW_FACTOR = 2.0  # Multiplier for order size adjustment based on inventory

# Smart buying: Only buy if it lowers average (prevents averaging up)
ONLY_AVERAGE_DOWN = True  # Set to False to allow buying at any price

# Stablecoin MM Strategy Parameters
MIN_SPREAD_BPS = 3  # Minimum spread in basis points (0.03%) to trade
INCREMENTAL_SELL = True  # Sell in tranches instead of all at once
SELL_TRANCHES = 4  # Number of sell levels (25% each)
TRANCHE_SPREAD_BPS = 2  # Additional spread per tranche in bps (0.02%)
INVENTORY_SKEW_THRESHOLD = 0.6  # At 60% of max position, start aggressive skewing
AVERAGE_DOWN_THRESHOLD_BPS = 5  # Only average down when high inventory if price is 20+ bps below average (0.2%)
TARGET_INVENTORY = 0  # Target neutral inventory

# Smart order management
REQUOTE_THRESHOLD_TICKS = 2  # Only requote if price moves >2 ticks
REQUOTE_ON_POSITION_CHANGE = True  # Requote when position changes
MAX_ORDER_AGE_SECONDS = 120  # Force requote after this time

# State tracking
position = 0  # Current inventory
average_buy_price = 0
active_orders = []
processed_trade_ids = set()  # Track which trades we've already processed

# Order management state
last_bid_price = None
last_ask_price = None
last_position = 0
last_orderbook_update = 0

# Database setup
def init_database():
    """Initialize SQLite database for trade tracking"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY,
            timestamp INTEGER,
            side TEXT,
            price REAL,
            amount REAL,
            cost REAL
        )
    ''')
    
    # Create position snapshots table for debugging
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS position_snapshots (
            timestamp INTEGER PRIMARY KEY,
            position REAL,
            average_buy_price REAL,
            usdc_balance REAL
        )
    ''')
    
    # Create market snapshots table for spread and volatility tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            mid_price REAL,
            best_bid REAL,
            best_ask REAL,
            spread_bps REAL,
            bid_depth_5 REAL,
            ask_depth_5 REAL
        )
    ''')
    
    # Create order events table for order lifecycle tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            order_id TEXT,
            event_type TEXT,
            side TEXT,
            price REAL,
            amount REAL,
            reason TEXT
        )
    ''')
    
    # Create daily metrics table for performance tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_metrics (
            date TEXT PRIMARY KEY,
            total_trades INTEGER,
            total_volume REAL,
            realized_profit REAL,
            fees_paid REAL,
            avg_spread_bps REAL,
            max_position REAL,
            min_position REAL
        )
    ''')
    
    # Create system events table for health monitoring
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER,
            event_type TEXT,
            severity TEXT,
            message TEXT,
            details TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def load_position_from_db():
    """Reconstruct position and average buy price from database"""
    global position, average_buy_price, processed_trade_ids
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all trades ordered by timestamp
    cursor.execute('SELECT trade_id, side, price, amount FROM trades ORDER BY timestamp')
    trades = cursor.fetchall()
    
    if not trades:
        log("📊 No previous trades found in database")
        conn.close()
        return
    
    # Reconstruct position and average
    calc_position = 0
    calc_avg = 0
    
    for trade_id, side, price, amount in trades:
        processed_trade_ids.add(trade_id)
        
        if side == 'buy':
            # Include maker fee in the cost basis
            price_with_fee = price * (1 + MAKER_FEE)
            total_cost = calc_avg * calc_position + price_with_fee * amount
            calc_position += amount
            calc_avg = total_cost / calc_position if calc_position > 0 else 0
        elif side == 'sell':
            calc_position -= amount
            if calc_position <= 0:
                calc_avg = 0
                calc_position = 0
    
    position = calc_position
    average_buy_price = calc_avg
    
    log(f"📊 Loaded from DB: {len(trades)} trades, Position: {position:.2f}, Avg: {average_buy_price:.5f}")
    conn.close()

def save_trade_to_db(trade):
    """Save a trade to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    trade_id = trade.get('id') or trade.get('order')
    
    try:
        cursor.execute('''
            INSERT INTO trades (trade_id, timestamp, side, price, amount, cost)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            trade_id,
            trade.get('timestamp', int(time.time() * 1000)),
            trade['side'],
            trade['price'],
            trade['amount'],
            trade.get('cost', trade['price'] * trade['amount'])
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Trade already exists
    finally:
        conn.close()

def save_position_snapshot(usdc_balance):
    """Save current position snapshot"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO position_snapshots (timestamp, position, average_buy_price, usdc_balance)
        VALUES (?, ?, ?, ?)
    ''', (int(time.time()), position, average_buy_price, usdc_balance))
    
    conn.commit()
    conn.close()

def save_market_snapshot(mid_price, best_bid, best_ask, spread_bps, bid_depth, ask_depth):
    """Save market snapshot for spread and volatility tracking"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO market_snapshots (timestamp, mid_price, best_bid, best_ask, spread_bps, bid_depth_5, ask_depth_5)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (int(time.time() * 1000), mid_price, best_bid, best_ask, spread_bps, bid_depth, ask_depth))
    
    conn.commit()
    conn.close()

def log_order_event(order_id, event_type, side, price, amount, reason=""):
    """Log order lifecycle events"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO order_events (timestamp, order_id, event_type, side, price, amount, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (int(time.time() * 1000), order_id, event_type, side, price, amount, reason))
    
    conn.commit()
    conn.close()

def log_system_event(event_type, severity, message, details=""):
    """Log system events for health monitoring"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO system_events (timestamp, event_type, severity, message, details)
        VALUES (?, ?, ?, ?, ?)
    ''', (int(time.time() * 1000), event_type, severity, message, details))
    
    conn.commit()
    conn.close()


# Fetch spot market
USDHL_MARKET_ID = ""
market = exchange.fetchMarkets()
for m in market:
    if m['spot']:
        if m['base'] == "USDHL":
            USDHL_MARKET_ID = m['id']
            print(f"Found market: {USDHL_MARKET_ID}")
            break

if not USDHL_MARKET_ID:
    raise Exception("USDHL market not found")

def log(message):
    """Print timestamped log message"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def should_requote(current_bid, current_ask, current_position):
    """Determine if we should cancel and replace orders"""
    global last_bid_price, last_ask_price, last_position, last_orderbook_update
    
    # First time or no previous orders
    if last_bid_price is None or last_ask_price is None:
        return True, "Initial order placement"
    
    # Check if position changed (fill detected)
    if REQUOTE_ON_POSITION_CHANGE and abs(current_position - last_position) > 0.1:
        return True, f"Position changed: {last_position:.2f} -> {current_position:.2f}"
    
    # Check if prices moved beyond threshold
    bid_moved = abs(current_bid - last_bid_price) if current_bid and last_bid_price else 0
    ask_moved = abs(current_ask - last_ask_price) if current_ask and last_ask_price else 0
    price_threshold = REQUOTE_THRESHOLD_TICKS * TICK_SIZE
    
    if bid_moved > price_threshold or ask_moved > price_threshold:
        return True, f"Price moved: bid {bid_moved/TICK_SIZE:.0f} ticks, ask {ask_moved/TICK_SIZE:.0f} ticks"
    
    # Check if orders are too old
    order_age = time.time() - last_orderbook_update
    if order_age > MAX_ORDER_AGE_SECONDS:
        return True, f"Orders aged out ({order_age:.0f}s > {MAX_ORDER_AGE_SECONDS}s)"
    
    return False, "No requote needed"

def cancel_all_orders():
    """Cancel all open orders"""
    global active_orders
    try:
        open_orders = exchange.fetchOpenOrders(USDHL_MARKET_ID)
        if len(open_orders) > 0:
            for order in open_orders:
                try:
                    exchange.cancelOrder(order['id'], USDHL_MARKET_ID)
                    log_order_event(order['id'], 'cancelled', order.get('side', 'unknown'), 
                                   order.get('price', 0), order.get('amount', 0), 'Requoting')
                    log(f"❌ Cancelled order {order['id']}")
                except Exception as e:
                    log(f"Error cancelling order {order['id']}: {e}")
        active_orders = []
    except Exception as e:
        log(f"Error fetching/cancelling orders: {e}")

def update_position():
    """Update current position and USDC balance"""
    global position, average_buy_price
    try:
        balance = exchange.fetch_balance({'type': 'spot'})
        # Use 'total' to include locked funds in open orders
        actual_position = balance.get('USDHL', {}).get('total', 0)
        usdc_balance = balance.get('USDC', {}).get('free', 0)
        
        # Always sync position from exchange (source of truth)
        # Exchange balance reflects locked amounts from open orders
        position_diff = abs(actual_position - position)
        if position_diff > 0.1:
            log(f"🔄 Position sync: Exchange: {actual_position:.2f}, Tracked: {position:.2f}, Diff: {position_diff:.2f}")
            
            # Critical mismatch - FIFO queue is now unreliable
            if position_diff > 100.0:  # Increased threshold - order placement causes temporary mismatches
                log(f"🛑 CRITICAL MISMATCH (>{position_diff:.2f} units)! HALTING TRADING.")
                log(f"🔧 Action required: Run reconciliation or restart bot after investigating.")
                raise Exception(f"Position mismatch too large: {position_diff:.2f} units. Manual intervention required.")
        
        # Always sync to exchange value
        position = actual_position
        
        # Save snapshot periodically
        save_position_snapshot(usdc_balance)
        
        # Log with average price if we have inventory
        if position > 0 and average_buy_price > 0:
            log(f"Position: {position:.2f} USDHL @ avg {average_buy_price:.5f} | USDC: {usdc_balance:.2f}")
        else:
            log(f"Position: {position:.2f} USDHL | USDC: {usdc_balance:.2f}")
        
        return position, usdc_balance
    except Exception as e:
        log(f"Error fetching balance: {e}")
        return position, 0

def calculate_order_sizes():
    """Calculate buy and sell order sizes based on inventory skew"""
    # Calculate inventory ratio: -1 (max short) to +1 (max long)
    inventory_ratio = position / MAX_POSITION if MAX_POSITION > 0 else 0
    inventory_ratio = max(-1, min(1, inventory_ratio))  # Clamp to [-1, 1]
    
    # Skew sizes: more inventory = larger sells, smaller buys
    buy_skew = 1 - (inventory_ratio * SKEW_FACTOR * 0.5)  # Reduce buys when long
    sell_skew = 1 + (inventory_ratio * SKEW_FACTOR * 0.5)  # Increase sells when long
    
    buy_size = ORDER_SIZE * max(0.2, buy_skew)  # Min 20% of base size
    sell_size = ORDER_SIZE * max(0.2, sell_skew)  # Min 20% of base size
    
    return round(buy_size, 3), round(sell_size, 3)

def calculate_order_prices(mid_price, lowest_ask, highest_bid, spread_bps):
    """Calculate bid and ask prices - stablecoin MM strategy"""
    
    # Calculate inventory ratio for skewing
    inventory_ratio = (position - TARGET_INVENTORY) / MAX_POSITION if MAX_POSITION > 0 else 0
    
    # Initialize prices
    bid_price = highest_bid
    ask_price = lowest_ask
    
    # Check if we can do inventory management actions (bypass spread check)
    can_average_down = False
    can_sell_profit = False
    
    if position > 0 and average_buy_price > 0:
        # Check if we can average down
        buy_price_with_fee = highest_bid * (1 + MAKER_FEE)
        can_average_down = buy_price_with_fee < average_buy_price
        
        # Check if we can sell at profit
        # average_buy_price already includes buy fee, so we just need to cover sell fee
        breakeven_price = average_buy_price / (1 - MAKER_FEE)
        can_sell_profit = lowest_ask >= breakeven_price
    
    # Only enforce MIN_SPREAD_BPS if we're NOT doing inventory management
    if spread_bps < MIN_SPREAD_BPS:
        if can_average_down or can_sell_profit:
            log(f"⚡ Spread tight ({spread_bps:.2f} bps) but inventory management available:")
            log_system_event('spread_check', 'warning', 
                           f"Spread tight ({spread_bps:.2f} bps) but inventory management available",
                           f"can_average_down={can_average_down}, can_sell_profit={can_sell_profit}")
            if can_average_down:
                log(f"   ✅ Can average down: {highest_bid:.5f} < avg {average_buy_price:.5f}")
            if can_sell_profit:
                log(f"   ✅ Can sell at profit: {lowest_ask:.5f} >= breakeven {breakeven_price:.5f}")
        else:
            log(f"⏸️ Spread too tight: {spread_bps:.2f} bps < {MIN_SPREAD_BPS} bps minimum (no inventory actions available)")
            log_system_event('spread_check', 'info', 
                           f"Spread too tight: {spread_bps:.2f} bps < {MIN_SPREAD_BPS} bps minimum - No trading", '')
            return None, None
    
    # Aggressive inventory management for stablecoins
    if abs(inventory_ratio) > INVENTORY_SKEW_THRESHOLD:
        if inventory_ratio > INVENTORY_SKEW_THRESHOLD:
            # Too long - only sell, no buying UNLESS price is significantly below average
            should_block_buy = True
            
            if can_average_down and average_buy_price > 0:
                # Calculate how much better the price is (in bps)
                buy_price_with_fee = bid_price * (1 + MAKER_FEE) if bid_price else highest_bid * (1 + MAKER_FEE)
                price_improvement_bps = ((average_buy_price - buy_price_with_fee) / average_buy_price) * 10000
                
                if price_improvement_bps >= AVERAGE_DOWN_THRESHOLD_BPS:
                    should_block_buy = False
                    log(f"⚡ High inventory ({position:.2f}) but price {price_improvement_bps:.1f} bps below avg - allowing buy")
                    log_system_event('inventory_management', 'warning', 
                                   f"High inventory ({position:.2f}) but allowing buy - price {price_improvement_bps:.1f} bps below avg", '')
                else:
                    log(f"⚠️ High inventory ({position:.2f}), price improvement {price_improvement_bps:.1f} bps < threshold {AVERAGE_DOWN_THRESHOLD_BPS} bps")
            
            if should_block_buy:
                log(f"⚠️ High inventory ({position:.2f}), only placing sell orders")
                log_system_event('inventory_management', 'warning', 
                               f"High inventory ({position:.2f}/{MAX_POSITION}) - Blocking buys, only selling", '')
                bid_price = None
    
    # Only place sell if we have inventory and it's profitable
    if ask_price and position > 0 and average_buy_price > 0:
        # Calculate breakeven price (average_buy_price already includes buy fee, just need to cover sell fee)
        breakeven_price = average_buy_price / (1 - MAKER_FEE)
        
        if ask_price >= breakeven_price:
            # Profitable - can sell
            profit_per_unit = ask_price * (1 - MAKER_FEE) - average_buy_price
            total_profit = profit_per_unit * position
            log(f"💰 Profitable sell opportunity: ask={ask_price:.5f} >= breakeven={breakeven_price:.5f}, profit=${total_profit:.2f}")
            log_system_event('sell_decision', 'info', 
                           f"Profitable sell: ask={ask_price:.5f} >= breakeven={breakeven_price:.5f}", 
                           f"Expected profit: ${total_profit:.2f}")
        else:
            # Not profitable yet - only place buy to average down
            log(f"⏸️ Waiting for profit: ask={ask_price:.5f} < breakeven={breakeven_price:.5f} (avg={average_buy_price:.5f})")
            log_system_event('sell_decision', 'info', 
                           f"Waiting for profit: ask={ask_price:.5f} < breakeven={breakeven_price:.5f}", '')
            ask_price = None
    
    return round(bid_price, 5) if bid_price else None, round(ask_price, 5) if ask_price else None

def place_orders(bid_price, ask_price, usdc_balance):
    """Place buy and sell limit orders with dynamic sizing"""
    global active_orders, position
    
    orders_placed = []
    
    # If both prices are None, skip order placement
    if bid_price is None and ask_price is None:
        log("⏸️ No orders to place this cycle")
        return orders_placed
    
    # Calculate skewed order sizes based on inventory
    buy_size, sell_size = calculate_order_sizes()
    
    # Calculate how much USDC we need for the buy order
    usdc_needed = buy_size * bid_price if bid_price else 0
    
    # Place buy order if we have enough USDC and haven't hit max position
    # Check if buy would lower average (if ONLY_AVERAGE_DOWN is enabled)
    should_buy = True
    if bid_price and ONLY_AVERAGE_DOWN and position > 0 and average_buy_price > 0:
        # Calculate what the buy price would be WITH fees included
        buy_price_with_fee = bid_price * (1 + MAKER_FEE)
        
        # Only buy if it would lower our average
        if buy_price_with_fee >= average_buy_price:
            should_buy = False
            log(f"⏸️ Skipping buy: price with fee {buy_price_with_fee:.5f} >= avg {average_buy_price:.5f} (would increase average)")
            log_system_event('buy_decision', 'info', 
                           f"Skipping buy: would increase average ({buy_price_with_fee:.5f} >= {average_buy_price:.5f})", '')
        else:
            # Calculate new average after this buy
            new_total_cost = average_buy_price * position + buy_price_with_fee * buy_size
            new_position = position + buy_size
            new_average = new_total_cost / new_position
            log(f"✅ Averaging down: {buy_price_with_fee:.5f} < {average_buy_price:.5f}, new avg will be {new_average:.5f}")
            log_system_event('buy_decision', 'info', 
                           f"Averaging down: {buy_price_with_fee:.5f} < {average_buy_price:.5f}, new avg: {new_average:.5f}", '')
    
    if bid_price and should_buy and position < MAX_POSITION and usdc_balance >= usdc_needed:
        # Don't place buy orders at or above 0.999
        if bid_price >= 0.999:
            log(f"⏸️ Skipping buy: price {bid_price:.5f} >= 0.999 threshold")
            log_system_event('buy_decision', 'info', 
                           f"Skipping buy: price {bid_price:.5f} >= 0.999 threshold", '')
        else:
            try:
                # Hyperliquid spot orders need specific params
                params = {'vaultAddress': None}  # Use wallet, not vault for spot
                order = exchange.create_order(
                    'USDHL/USDC', 
                    'limit', 
                    'buy', 
                    buy_size, 
                    bid_price,
                    params
                )
                orders_placed.append(order)
                log_order_event(order.get('id', 'unknown'), 'placed', 'buy', bid_price, buy_size, f"Cost: {usdc_needed:.2f} USDC")
                log(f"✅ BUY order placed: {buy_size} @ {bid_price} (Cost: {usdc_needed:.2f} USDC)")
            except Exception as e:
                log(f"❌ Error placing buy order: {e}")
    elif position >= MAX_POSITION:
        log(f"⚠️ Max position reached ({position:.2f}/{MAX_POSITION})")
    elif usdc_balance < usdc_needed:
        log(f"⚠️ Insufficient USDC: have {usdc_balance:.2f}, need {usdc_needed:.2f}")
    
    # Incremental selling strategy for stablecoins
    if ask_price and position > 0:
        min_order_value = 10.0
        
        if INCREMENTAL_SELL and position > 50:  # Only use tranches for larger positions
            # Sell in multiple tranches at different price levels
            breakeven_price = average_buy_price / (1 - MAKER_FEE)
            tranche_size = round(position / SELL_TRANCHES, 3)
            
            log(f"📊 Incremental selling: {SELL_TRANCHES} tranches of ~{tranche_size:.2f} USDHL each")
            
            for i in range(SELL_TRANCHES):
                # Each tranche at progressively better prices
                price_improvement_bps = i * TRANCHE_SPREAD_BPS
                tranche_price = ask_price * (1 + price_improvement_bps / 10000)
                
                # Ensure we're still profitable
                if tranche_price < breakeven_price:
                    continue
                
                # Last tranche gets any remainder
                if i == SELL_TRANCHES - 1:
                    tranche_size = round(position * 0.99, 3)  # Sell remaining
                
                order_value = tranche_size * tranche_price
                
                if order_value >= min_order_value and tranche_size >= 1:
                    try:
                        params = {'vaultAddress': None}
                        order = exchange.create_order(
                            'USDHL/USDC', 
                            'limit', 
                            'sell', 
                            tranche_size, 
                            round(tranche_price, 5),
                            params
                        )
                        orders_placed.append(order)
                        
                        sell_revenue_after_fee = tranche_price * (1 - MAKER_FEE)
                        expected_profit = (sell_revenue_after_fee - average_buy_price) * tranche_size
                        
                        log_order_event(order.get('id', 'unknown'), 'placed', 'sell', round(tranche_price, 5), tranche_size, 
                                       f"Tranche {i+1}/{SELL_TRANCHES}, +{price_improvement_bps} bps, profit: ${expected_profit:.4f}")
                        log(f"✅ SELL tranche {i+1}/{SELL_TRANCHES}: {tranche_size} @ {tranche_price:.5f} (+{price_improvement_bps} bps, profit: ${expected_profit:.4f})")
                    except Exception as e:
                        log(f"❌ Error placing sell tranche {i+1}: {e}")
        else:
            # Small position - sell all at once
            actual_sell_size = round(position * 0.99, 3)
            order_value = actual_sell_size * ask_price
            
            if order_value >= min_order_value and actual_sell_size >= 1:
                try:
                    params = {'vaultAddress': None}
                    order = exchange.create_order(
                        'USDHL/USDC', 
                        'limit', 
                        'sell', 
                        actual_sell_size, 
                        ask_price,
                        params
                    )
                    orders_placed.append(order)
                    
                    sell_revenue_after_fee = ask_price * (1 - MAKER_FEE)
                    expected_profit = (sell_revenue_after_fee - average_buy_price) * actual_sell_size
                    
                    log_order_event(order.get('id', 'unknown'), 'placed', 'sell', ask_price, actual_sell_size, 
                                   f"Profit: ${expected_profit:.4f}, Avg: {average_buy_price:.5f}")
                    log(f"✅ SELL order placed: {actual_sell_size} @ {ask_price} (Profit: ${expected_profit:.4f}, Avg: {average_buy_price:.5f})")
                except Exception as e:
                    log(f"❌ Error placing sell order: {e}")
    
    active_orders = orders_placed
    return orders_placed

def check_filled_orders():
    """Check if any orders were filled, log them, and update average buy price"""
    global average_buy_price, processed_trade_ids, position
    
    try:
        # Fetch recent trades
        trades = exchange.fetchMyTrades(USDHL_MARKET_ID, limit=20)
        
        # Process only new trades (ones we haven't seen before)
        for trade in trades:
            trade_id = trade.get('id') or trade.get('order')
            
            # Skip if we've already processed this trade
            if trade_id in processed_trade_ids:
                continue
            
            # Mark this trade as processed
            processed_trade_ids.add(trade_id)
            
            # Save trade to database
            save_trade_to_db(trade)
            
            if trade['side'] == 'buy':
                # Update average buy price based on this new buy (include maker fee in cost basis)
                # Note: position is already updated by update_position() from exchange balance
                price_with_fee = trade['price'] * (1 + MAKER_FEE)
                old_position = position - trade['amount']
                total_cost = average_buy_price * old_position + price_with_fee * trade['amount']
                average_buy_price = total_cost / position if position > 0 else 0
                
                log(f"📈 Buy filled: {trade['amount']} @ {trade['price']} (cost basis with fee: {price_with_fee:.5f}), New Avg: {average_buy_price:.5f}")
            
            elif trade['side'] == 'sell':
                # Calculate profit
                sell_revenue_after_fee = trade['price'] * (1 - MAKER_FEE)
                profit = (sell_revenue_after_fee - average_buy_price) * trade['amount']
                
                log(f"📉 Sell filled: {trade['amount']} @ {trade['price']}, Net profit: ${profit:.4f}")
                
                # Position is already updated by update_position() from exchange
                # Reset average if position is now near zero
                if position <= 5:  # Less than 5 USDHL remaining
                    average_buy_price = 0
                    log(f"🔄 Position cleared, resetting average")
        
        # Keep only recent trade IDs to prevent memory bloat (keep last 100)
        if len(processed_trade_ids) > 100:
            # Convert to list, keep last 50, convert back to set
            processed_trade_ids = set(list(processed_trade_ids)[-50:])
    
    except Exception as e:
        log(f"Error checking filled orders: {e}")

# Initialize database and load previous state
init_database()
load_position_from_db()

# Main market making loop
log("🚀 Starting stablecoin market making bot...")
log(f"Configuration: OrderSize={ORDER_SIZE}, MaxPos={MAX_POSITION}, TickSize={TICK_SIZE}")
log(f"Strategy: MinSpread={MIN_SPREAD_BPS}bps, Tranches={SELL_TRANCHES}, InventorySkew={INVENTORY_SKEW_THRESHOLD*100:.0f}%")
log(f"Smart Orders: RequoteThreshold={REQUOTE_THRESHOLD_TICKS} ticks, MaxAge={MAX_ORDER_AGE_SECONDS}s")
if ONLY_AVERAGE_DOWN:
    log("⚠️ ONLY_AVERAGE_DOWN ENABLED: Bot will only buy when price (with fees) is below current average")
if INCREMENTAL_SELL:
    log(f"✅ INCREMENTAL_SELL ENABLED: Selling in {SELL_TRANCHES} tranches with {TRANCHE_SPREAD_BPS}bps spacing")

try:
    while True:
        try:
            # Update position and get USDC balance
            position, usdc_balance = update_position()
            
            # Check for filled orders (position is now current)
            check_filled_orders()
            
            # Fetch current orderbook
            orderbook = exchange.fetchOrderBook(USDHL_MARKET_ID)
            lowest_ask = orderbook['asks'][0][0] if orderbook['asks'] else None
            highest_bid = orderbook['bids'][0][0] if orderbook['bids'] else None
            
            if not lowest_ask or not highest_bid:
                log("⚠️ Incomplete orderbook, skipping iteration")
                time.sleep(LOOP_INTERVAL)
                continue
            
            mid_price = (lowest_ask + highest_bid) / 2
            spread_pct = ((lowest_ask - highest_bid) / mid_price) * 100
            spread_bps = spread_pct * 100  # Convert to basis points
            
            # Calculate orderbook depth (top 5 levels)
            bid_depth = sum([level[1] for level in orderbook['bids'][:5]]) if len(orderbook['bids']) >= 5 else 0
            ask_depth = sum([level[1] for level in orderbook['asks'][:5]]) if len(orderbook['asks']) >= 5 else 0
            
            # Save market snapshot for analytics
            save_market_snapshot(mid_price, highest_bid, lowest_ask, spread_bps, bid_depth, ask_depth)
            
            # Check if we need to requote
            need_requote, reason = should_requote(highest_bid, lowest_ask, position)
            
            if need_requote:
                log(f"🔄 Requoting: {reason}")
                log(f"📊 Market: Bid={highest_bid:.5f}, Ask={lowest_ask:.5f}, Mid={mid_price:.5f}, Spread={spread_bps:.1f} bps")
                
                # Cancel existing orders
                cancel_all_orders()
                
                # Wait for cancellations to process
                time.sleep(0.3)
                
                # Calculate new order prices
                bid_price, ask_price = calculate_order_prices(mid_price, lowest_ask, highest_bid, spread_bps)
                
                # Place new orders
                orders = place_orders(bid_price, ask_price, usdc_balance)
                
                # Update tracking variables (use market prices, not our order prices which may be None)
                last_bid_price = highest_bid
                last_ask_price = lowest_ask
                last_position = position
                last_orderbook_update = time.time()
                
                # If we placed orders, wait a bit for potential fills
                if len(orders) > 0:
                    time.sleep(1)
            else:
                log(f"⏸️ Keeping orders: Market stable (bid={highest_bid:.5f}, ask={lowest_ask:.5f})")
            
            # Wait before next iteration
            time.sleep(LOOP_INTERVAL)
        
        except KeyboardInterrupt:
            log("⚠️ Keyboard interrupt received")
            raise
        
        except Exception as e:
            log(f"❌ Error in main loop: {e}")
            time.sleep(LOOP_INTERVAL)

except KeyboardInterrupt:
    log("🛑 Shutting down bot...")
    cancel_all_orders()
    log("✅ All orders cancelled. Bot stopped.")




    
