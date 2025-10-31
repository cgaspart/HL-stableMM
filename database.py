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
