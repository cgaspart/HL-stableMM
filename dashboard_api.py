from flask import Flask, jsonify, render_template
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import json
import os
import time

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

@app.route('/v2')
def index_v2():
    """Serve the new multi-page dashboard"""
    return render_template('dashboard_v2.html')

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

@app.route('/api/market/current')
def get_current_market():
    """Get current market state with live orderbook data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get latest market snapshot
    cursor.execute('''
        SELECT * FROM market_snapshots 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''')
    latest = cursor.fetchone()
    
    conn.close()
    
    if not latest:
        return jsonify({
            'mid_price': 0,
            'best_bid': 0,
            'best_ask': 0,
            'spread_bps': 0,
            'bid_depth': 0,
            'ask_depth': 0,
            'timestamp': None
        })
    
    return jsonify({
        'mid_price': latest['mid_price'],
        'best_bid': latest['best_bid'],
        'best_ask': latest['best_ask'],
        'spread_bps': latest['spread_bps'],
        'bid_depth': latest['bid_depth_5'],
        'ask_depth': latest['ask_depth_5'],
        'timestamp': latest['timestamp']
    })

@app.route('/api/market/spread_history')
def get_spread_history():
    """Get spread history over time"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get spread data for last 24 hours
    cursor.execute('''
        SELECT timestamp, spread_bps, mid_price
        FROM market_snapshots
        WHERE timestamp > ?
        ORDER BY timestamp ASC
    ''', (int(time.time() * 1000) - 24 * 60 * 60 * 1000,))
    
    history = []
    for row in cursor.fetchall():
        history.append({
            'timestamp': row['timestamp'],
            'spread_bps': row['spread_bps'],
            'mid_price': row['mid_price']
        })
    
    conn.close()
    return jsonify(history)

@app.route('/api/market/volatility')
def get_volatility():
    """Calculate market volatility metrics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get price data for last hour
    cursor.execute('''
        SELECT mid_price, timestamp
        FROM market_snapshots
        WHERE timestamp > ?
        ORDER BY timestamp ASC
    ''', (int(time.time() * 1000) - 60 * 60 * 1000,))
    
    prices = [row['mid_price'] for row in cursor.fetchall()]
    conn.close()
    
    if len(prices) < 2:
        return jsonify({
            'volatility_1h': 0,
            'price_change_1h': 0,
            'price_change_pct': 0,
            'high_1h': 0,
            'low_1h': 0
        })
    
    # Calculate volatility (standard deviation of returns)
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
    volatility = (sum(r**2 for r in returns) / len(returns)) ** 0.5 * 100
    
    return jsonify({
        'volatility_1h': round(volatility, 4),
        'price_change_1h': round(prices[-1] - prices[0], 5),
        'price_change_pct': round((prices[-1] - prices[0]) / prices[0] * 100, 2),
        'high_1h': round(max(prices), 5),
        'low_1h': round(min(prices), 5)
    })

@app.route('/api/performance/unrealized_pnl')
def get_unrealized_pnl():
    """Calculate unrealized P&L based on current market price"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current position
    cursor.execute('''
        SELECT position, average_buy_price
        FROM position_snapshots
        ORDER BY timestamp DESC
        LIMIT 1
    ''')
    position_data = cursor.fetchone()
    
    # Get current market price
    cursor.execute('''
        SELECT mid_price
        FROM market_snapshots
        ORDER BY timestamp DESC
        LIMIT 1
    ''')
    market_data = cursor.fetchone()
    
    conn.close()
    
    if not position_data or not market_data or position_data['position'] <= 0:
        return jsonify({
            'unrealized_pnl': 0,
            'unrealized_pnl_pct': 0,
            'current_value': 0,
            'cost_basis': 0
        })
    
    position = position_data['position']
    avg_price = position_data['average_buy_price']
    current_price = market_data['mid_price']
    
    # Calculate unrealized P&L (accounting for fees)
    cost_basis = avg_price * position
    current_value = current_price * (1 - MAKER_FEE) * position  # After sell fee
    unrealized_pnl = current_value - cost_basis
    unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
    
    return jsonify({
        'unrealized_pnl': round(unrealized_pnl, 4),
        'unrealized_pnl_pct': round(unrealized_pnl_pct, 2),
        'current_value': round(current_value, 2),
        'cost_basis': round(cost_basis, 2),
        'position': position,
        'avg_price': avg_price,
        'current_price': current_price
    })

@app.route('/api/performance/stats')
def get_performance_stats():
    """Calculate advanced performance statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all trades
    cursor.execute('''
        SELECT side, price, amount, cost, timestamp
        FROM trades
        ORDER BY timestamp ASC
    ''')
    trades = cursor.fetchall()
    
    conn.close()
    
    if not trades:
        return jsonify({
            'profit_factor': 0,
            'roi_pct': 0,
            'total_fees': 0,
            'avg_profit_per_trade': 0,
            'win_rate': 0,
            'total_winning_trades': 0,
            'total_losing_trades': 0
        })
    
    # Calculate profit factor and other metrics
    buy_queue = []
    total_profit = 0
    total_loss = 0
    winning_trades = 0
    losing_trades = 0
    total_fees = 0
    
    for trade in trades:
        fee = trade['cost'] * MAKER_FEE
        total_fees += fee
        
        if trade['side'] == 'buy':
            price_with_fee = trade['price'] * (1 + MAKER_FEE)
            buy_queue.append({'price': price_with_fee, 'amount': trade['amount']})
        elif trade['side'] == 'sell' and buy_queue:
            sell_amount = trade['amount']
            sell_price = trade['price'] * (1 - MAKER_FEE)
            
            while sell_amount > 0 and buy_queue:
                buy = buy_queue[0]
                matched_amount = min(sell_amount, buy['amount'])
                profit = matched_amount * (sell_price - buy['price'])
                
                if profit > 0:
                    total_profit += profit
                    winning_trades += 1
                else:
                    total_loss += abs(profit)
                    losing_trades += 1
                
                sell_amount -= matched_amount
                buy['amount'] -= matched_amount
                
                if buy['amount'] <= 0:
                    buy_queue.pop(0)
    
    profit_factor = total_profit / total_loss if total_loss > 0 else (total_profit if total_profit > 0 else 0)
    total_trades = winning_trades + losing_trades
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Calculate ROI (assuming initial capital from first trades)
    initial_capital = sum(t['cost'] for t in trades[:10] if t['side'] == 'buy')
    roi_pct = (total_profit / initial_capital * 100) if initial_capital > 0 else 0
    
    avg_profit = total_profit / total_trades if total_trades > 0 else 0
    
    return jsonify({
        'profit_factor': round(profit_factor, 2),
        'roi_pct': round(roi_pct, 2),
        'total_fees': round(total_fees, 4),
        'avg_profit_per_trade': round(avg_profit, 4),
        'win_rate': round(win_rate, 1),
        'total_winning_trades': winning_trades,
        'total_losing_trades': losing_trades,
        'gross_profit': round(total_profit, 4),
        'gross_loss': round(total_loss, 4)
    })

@app.route('/api/performance/pnl_breakdown')
def get_pnl_breakdown():
    """Get P&L breakdown by day, week, month"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all trades
    cursor.execute('''
        SELECT side, price, amount, cost, timestamp
        FROM trades
        ORDER BY timestamp ASC
    ''')
    trades = cursor.fetchall()
    
    conn.close()
    
    # Calculate P&L by period
    daily_pnl = {}
    weekly_pnl = {}
    monthly_pnl = {}
    
    buy_queue = []
    
    for trade in trades:
        timestamp = trade['timestamp']
        date = datetime.fromtimestamp(timestamp / 1000)
        day_key = date.strftime('%Y-%m-%d')
        week_key = date.strftime('%Y-W%U')
        month_key = date.strftime('%Y-%m')
        
        if trade['side'] == 'buy':
            price_with_fee = trade['price'] * (1 + MAKER_FEE)
            buy_queue.append({'price': price_with_fee, 'amount': trade['amount'], 'date': day_key})
        elif trade['side'] == 'sell' and buy_queue:
            sell_amount = trade['amount']
            sell_price = trade['price'] * (1 - MAKER_FEE)
            
            while sell_amount > 0 and buy_queue:
                buy = buy_queue[0]
                matched_amount = min(sell_amount, buy['amount'])
                profit = matched_amount * (sell_price - buy['price'])
                
                # Add to daily
                if day_key not in daily_pnl:
                    daily_pnl[day_key] = 0
                daily_pnl[day_key] += profit
                
                # Add to weekly
                if week_key not in weekly_pnl:
                    weekly_pnl[week_key] = 0
                weekly_pnl[week_key] += profit
                
                # Add to monthly
                if month_key not in monthly_pnl:
                    monthly_pnl[month_key] = 0
                monthly_pnl[month_key] += profit
                
                sell_amount -= matched_amount
                buy['amount'] -= matched_amount
                
                if buy['amount'] <= 0:
                    buy_queue.pop(0)
    
    # Format response
    daily = [{'period': k, 'pnl': round(v, 4)} for k, v in sorted(daily_pnl.items())]
    weekly = [{'period': k, 'pnl': round(v, 4)} for k, v in sorted(weekly_pnl.items())]
    monthly = [{'period': k, 'pnl': round(v, 4)} for k, v in sorted(monthly_pnl.items())]
    
    return jsonify({
        'daily': daily,
        'weekly': weekly,
        'monthly': monthly
    })

@app.route('/api/system/health')
def get_system_health():
    """Get system health metrics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get latest position snapshot
    cursor.execute('''
        SELECT timestamp FROM position_snapshots
        ORDER BY timestamp DESC LIMIT 1
    ''')
    last_position_update = cursor.fetchone()
    
    # Get latest trade
    cursor.execute('''
        SELECT timestamp FROM trades
        ORDER BY timestamp DESC LIMIT 1
    ''')
    last_trade = cursor.fetchone()
    
    # Get recent system events
    cursor.execute('''
        SELECT event_type, severity, message, timestamp
        FROM system_events
        WHERE timestamp > ?
        ORDER BY timestamp DESC
        LIMIT 10
    ''', (int(time.time() * 1000) - 60 * 60 * 1000,))
    recent_events = cursor.fetchall()
    
    # Count errors in last hour
    cursor.execute('''
        SELECT COUNT(*) as error_count
        FROM system_events
        WHERE severity = 'error' AND timestamp > ?
    ''', (int(time.time() * 1000) - 60 * 60 * 1000,))
    error_count = cursor.fetchone()['error_count']
    
    conn.close()
    
    # Calculate uptime metrics
    now = int(time.time())
    last_update_seconds = now - last_position_update['timestamp'] if last_position_update else 999999
    last_trade_seconds = (now * 1000 - last_trade['timestamp']) / 1000 if last_trade else 999999
    
    # Determine health status
    if last_update_seconds > 60:
        status = 'error'
        status_message = 'Bot not responding'
    elif error_count > 5:
        status = 'warning'
        status_message = 'Multiple errors detected'
    elif last_trade_seconds > 600:
        status = 'warning'
        status_message = 'No recent trades'
    else:
        status = 'healthy'
        status_message = 'All systems operational'
    
    events = [{
        'type': e['event_type'],
        'severity': e['severity'],
        'message': e['message'],
        'timestamp': e['timestamp']
    } for e in recent_events]
    
    return jsonify({
        'status': status,
        'status_message': status_message,
        'last_update_seconds': int(last_update_seconds),
        'last_trade_seconds': int(last_trade_seconds),
        'error_count_1h': error_count,
        'recent_events': events
    })

if __name__ == '__main__':
    # Bind to 0.0.0.0 to be accessible from outside container
    # Use port 80 for Traefik compatibility
    port = int(os.getenv('FLASK_PORT', '80'))
    app.run(host='0.0.0.0', port=port, debug=False)
