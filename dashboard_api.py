from flask import Flask, jsonify, render_template
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import json
import os

# Database configuration
DB_PATH = os.getenv('DB_PATH', 'market_maker.db')

app = Flask(__name__)
CORS(app)

# Configuration - must match main.py
MAKER_FEE = 0.0004  # 0.04% maker fee for Hyperliquid spot

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return render_template('dashboard.html')

@app.route('/test')
def test():
    """Serve the API test page"""
    with open('test_api.html', 'r') as f:
        return f.read()

@app.route('/api/stats')
def get_stats():
    """Get current bot statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get latest position snapshot
    cursor.execute('''
        SELECT * FROM position_snapshots 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''')
    latest_snapshot = cursor.fetchone()
    
    # Get total trades
    cursor.execute('SELECT COUNT(*) as total FROM trades')
    total_trades = cursor.fetchone()['total']
    
    # Get buy/sell counts
    cursor.execute("SELECT COUNT(*) as buys FROM trades WHERE side = 'buy'")
    total_buys = cursor.fetchone()['buys']
    
    cursor.execute("SELECT COUNT(*) as sells FROM trades WHERE side = 'sell'")
    total_sells = cursor.fetchone()['sells']
    
    # Calculate total volume
    cursor.execute('SELECT SUM(cost) as volume FROM trades')
    total_volume = cursor.fetchone()['volume'] or 0
    
    # Calculate realized profit (from completed sell trades)
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN side = 'sell' THEN cost ELSE 0 END) as total_sell_value,
            SUM(CASE WHEN side = 'buy' THEN cost ELSE 0 END) as total_buy_value
        FROM trades
    ''')
    profit_data = cursor.fetchone()
    
    # Get recent trades for profit calculation
    cursor.execute('''
        SELECT side, price, amount, cost, timestamp
        FROM trades
        ORDER BY timestamp DESC
        LIMIT 100
    ''')
    recent_trades = cursor.fetchall()
    
    # Calculate approximate realized profit
    realized_profit = 0
    if recent_trades:
        buy_queue = []
        for trade in reversed(list(recent_trades)):
            if trade['side'] == 'buy':
                buy_queue.append({'price': trade['price'], 'amount': trade['amount']})
            elif trade['side'] == 'sell' and buy_queue:
                sell_amount = trade['amount']
                sell_price = trade['price']
                
                while sell_amount > 0 and buy_queue:
                    buy = buy_queue[0]
                    matched_amount = min(sell_amount, buy['amount'])
                    # Calculate net profit after fees
                    buy_cost_with_fee = buy['price'] * (1 + MAKER_FEE)
                    sell_revenue_after_fee = sell_price * (1 - MAKER_FEE)
                    realized_profit += matched_amount * (sell_revenue_after_fee - buy_cost_with_fee)
                    
                    sell_amount -= matched_amount
                    buy['amount'] -= matched_amount
                    
                    if buy['amount'] <= 0:
                        buy_queue.pop(0)
    
    conn.close()
    
    stats = {
        'current_position': latest_snapshot['position'] if latest_snapshot else 0,
        'average_buy_price': latest_snapshot['average_buy_price'] if latest_snapshot else 0,
        'usdc_balance': latest_snapshot['usdc_balance'] if latest_snapshot else 0,
        'total_trades': total_trades,
        'total_buys': total_buys,
        'total_sells': total_sells,
        'total_volume': round(total_volume, 2),
        'realized_profit': round(realized_profit, 4),
        'last_update': latest_snapshot['timestamp'] if latest_snapshot else None
    }
    
    return jsonify(stats)

@app.route('/api/trades/recent')
def get_recent_trades():
    """Get recent trades"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT trade_id, timestamp, side, price, amount, cost
        FROM trades
        ORDER BY timestamp DESC
        LIMIT 50
    ''')
    
    trades = []
    for row in cursor.fetchall():
        trades.append({
            'trade_id': row['trade_id'],
            'timestamp': row['timestamp'],
            'side': row['side'],
            'price': row['price'],
            'amount': row['amount'],
            'cost': row['cost']
        })
    
    conn.close()
    return jsonify(trades)

@app.route('/api/trades/history')
def get_trade_history():
    """Get trade history for charts"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all trades
    cursor.execute('''
        SELECT timestamp, side, price, amount, cost
        FROM trades
        ORDER BY timestamp ASC
    ''')
    
    trades = cursor.fetchall()
    
    # Group by hour for performance chart
    hourly_data = {}
    cumulative_profit = 0
    buy_queue = []
    
    for trade in trades:
        # Trade timestamps are in milliseconds, convert to seconds first
        timestamp_seconds = int(trade['timestamp']) // 1000
        hour_key = (timestamp_seconds // 3600) * 3600  # Round to hour (in seconds)
        
        if hour_key not in hourly_data:
            hourly_data[hour_key] = {
                'timestamp': hour_key * 1000,  # Convert seconds to milliseconds for JS
                'volume': 0,
                'trades': 0,
                'profit': 0
            }
        
        hourly_data[hour_key]['volume'] += trade['cost']
        hourly_data[hour_key]['trades'] += 1
        
        # Calculate profit
        if trade['side'] == 'buy':
            buy_queue.append({'price': trade['price'], 'amount': trade['amount']})
        elif trade['side'] == 'sell' and buy_queue:
            sell_amount = trade['amount']
            sell_price = trade['price']
            
            while sell_amount > 0 and buy_queue:
                buy = buy_queue[0]
                matched_amount = min(sell_amount, buy['amount'])
                # Calculate net profit after fees
                buy_cost_with_fee = buy['price'] * (1 + MAKER_FEE)
                sell_revenue_after_fee = sell_price * (1 - MAKER_FEE)
                profit = matched_amount * (sell_revenue_after_fee - buy_cost_with_fee)
                cumulative_profit += profit
                hourly_data[hour_key]['profit'] += profit
                
                sell_amount -= matched_amount
                buy['amount'] -= matched_amount
                
                if buy['amount'] <= 0:
                    buy_queue.pop(0)
    
    conn.close()
    
    # Convert to list and add cumulative profit
    history = []
    running_profit = 0
    for timestamp in sorted(hourly_data.keys()):
        data = hourly_data[timestamp]
        running_profit += data['profit']
        history.append({
            'timestamp': data['timestamp'],
            'volume': round(data['volume'], 2),
            'trades': data['trades'],
            'profit': round(data['profit'], 4),
            'cumulative_profit': round(running_profit, 4)
        })
    
    return jsonify(history)

@app.route('/api/position/history')
def get_position_history():
    """Get position history over time"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT timestamp, position, average_buy_price, usdc_balance
        FROM position_snapshots
        ORDER BY timestamp ASC
    ''')
    
    history = []
    for row in cursor.fetchall():
        history.append({
            'timestamp': row['timestamp'] * 1000,  # Convert to milliseconds
            'position': row['position'],
            'average_buy_price': row['average_buy_price'],
            'usdc_balance': row['usdc_balance']
        })
    
    conn.close()
    return jsonify(history)

@app.route('/api/positions/open')
def get_open_positions():
    """Get current open positions (FIFO queue)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get open positions ordered by timestamp (FIFO)
    cursor.execute('''
        SELECT 
            id,
            trade_id,
            timestamp,
            amount,
            price_with_fee,
            remaining_amount
        FROM open_positions
        WHERE remaining_amount > 0
        ORDER BY timestamp ASC
    ''')
    
    positions = []
    total_amount = 0
    total_cost = 0
    
    for row in cursor.fetchall():
        remaining = row['remaining_amount']
        price = row['price_with_fee']
        
        # Calculate minimum profitable sell price (need to cover sell fee)
        min_profitable_price = price * (1 + MAKER_FEE)
        
        positions.append({
            'id': row['id'],
            'trade_id': row['trade_id'],
            'timestamp': row['timestamp'],
            'original_amount': row['amount'],
            'remaining_amount': remaining,
            'price_with_fee': price,
            'min_profitable_price': min_profitable_price,
            'cost_basis': remaining * price
        })
        
        total_amount += remaining
        total_cost += remaining * price
    
    # Calculate average
    average_price = total_cost / total_amount if total_amount > 0 else 0
    
    conn.close()
    
    return jsonify({
        'positions': positions,
        'summary': {
            'total_positions': len(positions),
            'total_amount': round(total_amount, 2),
            'average_price': round(average_price, 5),
            'total_cost_basis': round(total_cost, 2)
        }
    })

if __name__ == '__main__':
    # Bind to 0.0.0.0 to be accessible from outside container
    # Use port 80 for Traefik compatibility
    port = int(os.getenv('FLASK_PORT', '80'))
    app.run(host='0.0.0.0', port=port, debug=False)
