"""
Database module for trade tracking, position snapshots, and system events
"""
import sqlite3
import time
from config import DB_PATH
from logger import log


def get_db_connection():
    """Get database connection with proper timeout and WAL mode"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    # Enable WAL mode for better concurrency
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')  # 30 second timeout
    return conn


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
    
    # Create grid orders table for tracking paired buy/sell orders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grid_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grid_id TEXT NOT NULL,
            level_index INTEGER,
            buy_order_id TEXT,
            sell_order_id TEXT,
            buy_price REAL,
            sell_price REAL,
            size REAL,
            status TEXT,
            buy_filled_at INTEGER,
            sell_filled_at INTEGER,
            profit REAL,
            created_at INTEGER,
            updated_at INTEGER
        )
    ''')
    
    # Create grid state table for tracking grid configuration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grid_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grid_id TEXT UNIQUE NOT NULL,
            center_price REAL,
            num_levels INTEGER,
            grid_spacing_bps REAL,
            profit_target_bps REAL,
            created_at INTEGER,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()


def save_trade_to_db(trade: dict) -> None:
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


def save_position_snapshot(position: float, average_buy_price: float, usdc_balance: float) -> None:
    """Save current position snapshot"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO position_snapshots (timestamp, position, average_buy_price, usdc_balance)
        VALUES (?, ?, ?, ?)
    ''', (int(time.time()), position, average_buy_price, usdc_balance))
    
    conn.commit()
    conn.close()


def save_market_snapshot(mid_price: float, best_bid: float, best_ask: float, 
                        spread_bps: float, bid_depth: float, ask_depth: float) -> None:
    """Save market snapshot for spread and volatility tracking"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO market_snapshots (timestamp, mid_price, best_bid, best_ask, spread_bps, bid_depth_5, ask_depth_5)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (int(time.time() * 1000), mid_price, best_bid, best_ask, spread_bps, bid_depth, ask_depth))
    
    conn.commit()
    conn.close()


def log_order_event(order_id: str, event_type: str, side: str, price: float, 
                   amount: float, reason: str = "") -> None:
    """Log order lifecycle events"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO order_events (timestamp, order_id, event_type, side, price, amount, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (int(time.time() * 1000), order_id, event_type, side, price, amount, reason))
    
    conn.commit()
    conn.close()


def log_system_event(event_type: str, severity: str, message: str, details: str = "") -> None:
    """Log system events for health monitoring"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO system_events (timestamp, event_type, severity, message, details)
        VALUES (?, ?, ?, ?, ?)
    ''', (int(time.time() * 1000), event_type, severity, message, details))
    
    conn.commit()
    conn.close()


def load_trades_from_db() -> list:
    """Load all trades from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT trade_id, side, price, amount FROM trades ORDER BY timestamp')
    trades = cursor.fetchall()
    conn.close()
    
    return trades


# ============================================================================
# GRID TRADING DATABASE FUNCTIONS
# ============================================================================

def save_grid_state(grid_id: str, center_price: float, num_levels: int, 
                   grid_spacing_bps: float, profit_target_bps: float) -> None:
    """Save grid configuration state"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO grid_state 
        (grid_id, center_price, num_levels, grid_spacing_bps, profit_target_bps, created_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    ''', (grid_id, center_price, num_levels, grid_spacing_bps, profit_target_bps, int(time.time())))
    
    conn.commit()
    conn.close()


def deactivate_grid(grid_id: str) -> None:
    """Mark a grid as inactive"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE grid_state SET is_active = 0 WHERE grid_id = ?', (grid_id,))
    
    conn.commit()
    conn.close()


def save_grid_order(grid_id: str, level_index: int, buy_order_id: str, sell_order_id: str,
                   buy_price: float, sell_price: float, size: float, status: str) -> None:
    """Save a grid order pair"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = int(time.time() * 1000)
    cursor.execute('''
        INSERT INTO grid_orders 
        (grid_id, level_index, buy_order_id, sell_order_id, buy_price, sell_price, 
         size, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (grid_id, level_index, buy_order_id, sell_order_id, buy_price, sell_price, 
          size, status, now, now))
    
    conn.commit()
    conn.close()


def update_grid_order_status(order_id: str, is_buy: bool, filled_at: int = None, 
                            profit: float = None) -> None:
    """Update grid order when filled"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = int(time.time() * 1000)
    
    if is_buy:
        cursor.execute('''
            UPDATE grid_orders 
            SET buy_filled_at = ?, status = 'buy_filled', updated_at = ?
            WHERE buy_order_id = ?
        ''', (filled_at or now, now, order_id))
    else:
        cursor.execute('''
            UPDATE grid_orders 
            SET sell_filled_at = ?, profit = ?, status = 'completed', updated_at = ?
            WHERE sell_order_id = ?
        ''', (filled_at or now, profit, now, order_id))
    
    conn.commit()
    conn.close()


def get_active_grid_orders(grid_id: str) -> list:
    """Get all active grid orders for a grid"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, level_index, buy_order_id, sell_order_id, buy_price, sell_price, 
               size, status, buy_filled_at, sell_filled_at
        FROM grid_orders 
        WHERE grid_id = ? AND status != 'completed'
        ORDER BY level_index
    ''', (grid_id,))
    
    orders = cursor.fetchall()
    conn.close()
    
    return orders


def get_grid_performance(grid_id: str) -> dict:
    """Get performance metrics for a grid"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total_orders,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
            SUM(CASE WHEN profit IS NOT NULL THEN profit ELSE 0 END) as total_profit
        FROM grid_orders 
        WHERE grid_id = ?
    ''', (grid_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    return {
        'total_orders': result[0] if result else 0,
        'completed_orders': result[1] if result else 0,
        'total_profit': result[2] if result else 0
    }
