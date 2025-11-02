"""
Grid Trading Strategy Module
Implements independent buy/sell pairs for stablecoin market making
Each grid level operates independently with its own P&L tracking
"""
import time
import uuid
from typing import Dict, List, Tuple, Optional
from config import (
    GRID_LEVELS, GRID_SIZE, GRID_SPACING_BPS, PROFIT_TARGET_BPS,
    MAX_GRID_POSITION, GRID_REBALANCE_THRESHOLD_BPS, GRID_MIN_ORDER_VALUE,
    GRID_PLACE_BOTH_SIDES, GRID_MAX_BUY_PRICE, MAKER_FEE
)
from logger import log
from database import (
    save_grid_state, save_grid_order, update_grid_order_status,
    get_active_grid_orders, get_grid_performance, deactivate_grid,
    save_trade_to_db, log_system_event
)


class GridLevel:
    """Represents a single grid level with buy/sell pair"""
    
    def __init__(self, level_index: int, buy_price: float, sell_price: float, size: float):
        self.level_index = level_index
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.size = size
        self.buy_order_id: Optional[str] = None
        self.sell_order_id: Optional[str] = None
        self.status = 'pending'  # pending, buy_placed, buy_filled, sell_placed, completed
        self.buy_filled_at: Optional[int] = None
        self.sell_filled_at: Optional[int] = None
        self.profit: float = 0
    
    def __repr__(self):
        return f"GridLevel({self.level_index}: buy={self.buy_price:.5f}, sell={self.sell_price:.5f}, status={self.status})"


class GridStrategy:
    """Grid trading strategy with independent buy/sell pairs"""
    
    def __init__(self):
        self.grid_id = f"grid_{int(time.time())}"
        self.center_price: float = 0
        self.grid_levels: List[GridLevel] = []
        self.position: float = 0
        self.processed_trade_ids = set()
        
    def initialize_grid(self, mid_price: float) -> None:
        """Initialize grid centered around mid price
        
        Args:
            mid_price: Current market mid price
        """
        # For stablecoins, cap center price to avoid buying above peg
        if mid_price > GRID_MAX_BUY_PRICE:
            log(f"⚠️ Mid price {mid_price:.5f} above max {GRID_MAX_BUY_PRICE:.5f}, capping center price")
            mid_price = GRID_MAX_BUY_PRICE
        
        self.center_price = mid_price
        self.grid_levels = []
        
        log(f"🔷 Initializing grid centered at {mid_price:.5f}")
        log(f"   Levels: {GRID_LEVELS}, Spacing: {GRID_SPACING_BPS} bps, Profit: {PROFIT_TARGET_BPS} bps")
        
        # Calculate grid levels symmetrically around center
        half_levels = GRID_LEVELS // 2
        
        for i in range(-half_levels, half_levels):
            # Calculate buy price (below center for negative i, above for positive)
            price_offset_bps = i * GRID_SPACING_BPS
            buy_price = mid_price * (1 + price_offset_bps / 10000)
            
            # For stablecoins, never buy above max price
            if buy_price > GRID_MAX_BUY_PRICE:
                log(f"   ⏸️ Skipping level {i}: buy price {buy_price:.5f} > {GRID_MAX_BUY_PRICE:.5f}")
                continue
            
            # Calculate sell price (buy price + profit target)
            sell_price = buy_price * (1 + PROFIT_TARGET_BPS / 10000)
            
            # Round to tick size
            buy_price = round(buy_price, 5)
            sell_price = round(sell_price, 5)
            
            level = GridLevel(
                level_index=i + half_levels,
                buy_price=buy_price,
                sell_price=sell_price,
                size=GRID_SIZE
            )
            self.grid_levels.append(level)
        
        # Save grid state to database
        save_grid_state(self.grid_id, self.center_price, GRID_LEVELS, 
                       GRID_SPACING_BPS, PROFIT_TARGET_BPS)
        
        log(f"✅ Grid initialized: {len(self.grid_levels)} levels")
        log(f"   Price range: {self.grid_levels[0].buy_price:.5f} - {self.grid_levels[-1].sell_price:.5f}")
    
    def should_rebalance_grid(self, current_mid_price: float) -> bool:
        """Check if grid needs rebalancing due to price movement
        
        Args:
            current_mid_price: Current market mid price
            
        Returns:
            bool: True if grid should be rebalanced
        """
        if not self.center_price:
            return True
        
        # Calculate price movement in bps
        price_move_bps = abs((current_mid_price - self.center_price) / self.center_price) * 10000
        
        if price_move_bps > GRID_REBALANCE_THRESHOLD_BPS:
            log(f"⚠️ Grid rebalance needed: price moved {price_move_bps:.1f} bps from center")
            log(f"   Center: {self.center_price:.5f}, Current: {current_mid_price:.5f}")
            return True
        
        return False
    
    def place_grid_orders(self, exchange, usdc_balance: float) -> int:
        """Place all grid orders on the exchange
        
        Args:
            exchange: HyperliquidExchange instance
            usdc_balance: Available USDC balance
            
        Returns:
            int: Number of orders placed
        """
        orders_placed = 0
        total_usdc_needed = 0
        
        # Calculate total USDC needed for all buy orders
        for level in self.grid_levels:
            total_usdc_needed += level.buy_price * level.size
        
        if total_usdc_needed > usdc_balance:
            log(f"⚠️ Insufficient USDC for full grid: need ${total_usdc_needed:.2f}, have ${usdc_balance:.2f}")
            log(f"   Placing partial grid with available balance")
        
        for level in self.grid_levels:
            # Skip if level already has active orders (buy filled waiting for sell)
            if level.status in ['buy_filled', 'sell_placed']:
                log(f"  ⏸️ Skipping L{level.level_index}: status={level.status}, waiting for sell to complete")
                continue
            
            # Check position limit
            if self.position >= MAX_GRID_POSITION:
                log(f"⚠️ Max position reached ({self.position:.2f}/{MAX_GRID_POSITION}), skipping remaining buy orders")
                break
            
            # Safety check: never buy above max price for stablecoins
            if level.buy_price > GRID_MAX_BUY_PRICE:
                log(f"  ⚠️ Skipping L{level.level_index}: buy price {level.buy_price:.5f} > {GRID_MAX_BUY_PRICE:.5f}")
                continue
            
            # Place buy order
            usdc_needed = level.buy_price * level.size
            order_value = level.size * level.buy_price
            
            if order_value >= GRID_MIN_ORDER_VALUE and usdc_balance >= usdc_needed:
                try:
                    buy_order = exchange.create_order('buy', level.size, level.buy_price)
                    level.buy_order_id = buy_order.get('id', f"buy_{level.level_index}")
                    level.status = 'buy_placed'
                    usdc_balance -= usdc_needed
                    orders_placed += 1
                    
                    log(f"  ✅ Buy L{level.level_index}: {level.size} @ {level.buy_price:.5f} (${usdc_needed:.2f})")
                    
                    # Place paired sell order if configured
                    if GRID_PLACE_BOTH_SIDES:
                        try:
                            sell_order = exchange.create_order('sell', level.size, level.sell_price)
                            level.sell_order_id = sell_order.get('id', f"sell_{level.level_index}")
                            orders_placed += 1
                            
                            expected_profit = (level.sell_price * (1 - MAKER_FEE) - level.buy_price * (1 + MAKER_FEE)) * level.size
                            log(f"  ✅ Sell L{level.level_index}: {level.size} @ {level.sell_price:.5f} (profit: ${expected_profit:.4f})")
                        except Exception as e:
                            log(f"  ❌ Error placing sell order L{level.level_index}: {e}")
                    
                    # Save to database
                    save_grid_order(
                        self.grid_id, level.level_index,
                        level.buy_order_id, level.sell_order_id or '',
                        level.buy_price, level.sell_price,
                        level.size, level.status
                    )
                    
                except Exception as e:
                    log(f"  ❌ Error placing buy order L{level.level_index}: {e}")
            else:
                if order_value < GRID_MIN_ORDER_VALUE:
                    log(f"  ⏸️ Skipping L{level.level_index}: order value ${order_value:.2f} < min ${GRID_MIN_ORDER_VALUE:.2f}")
                else:
                    log(f"  ⏸️ Skipping L{level.level_index}: insufficient USDC (need ${usdc_needed:.2f}, have ${usdc_balance:.2f})")
        
        log(f"📊 Grid orders placed: {orders_placed} orders")
        return orders_placed
    
    def check_filled_orders(self, exchange) -> None:
        """Check for filled orders and manage grid state
        
        Args:
            exchange: HyperliquidExchange instance
        """
        trades = exchange.fetch_my_trades(limit=50)
        
        # Sort trades by timestamp
        trades_sorted = sorted(trades, key=lambda t: t.get('timestamp', 0))
        
        for trade in trades_sorted:
            trade_id = trade.get('id') or trade.get('order')
            
            if trade_id in self.processed_trade_ids:
                continue
            
            self.processed_trade_ids.add(trade_id)
            save_trade_to_db(trade)
            
            # Find matching grid level
            for level in self.grid_levels:
                # Check if this is a buy order fill
                if level.buy_order_id and trade_id == level.buy_order_id:
                    self._handle_buy_fill(exchange, level, trade)
                    break
                
                # Check if this is a sell order fill
                if level.sell_order_id and trade_id == level.sell_order_id:
                    self._handle_sell_fill(exchange, level, trade)
                    break
        
        # Prevent memory bloat
        if len(self.processed_trade_ids) > 200:
            self.processed_trade_ids = set(list(self.processed_trade_ids)[-100:])
    
    def _handle_buy_fill(self, exchange, level: GridLevel, trade: dict) -> None:
        """Handle a buy order fill
        
        Args:
            exchange: HyperliquidExchange instance
            level: Grid level that was filled
            trade: Trade data
        """
        level.buy_filled_at = trade.get('timestamp', int(time.time() * 1000))
        level.status = 'buy_filled'
        self.position += trade['amount']
        
        buy_cost_with_fee = trade['price'] * (1 + MAKER_FEE)
        log(f"📈 Grid Buy Filled L{level.level_index}: {trade['amount']} @ {trade['price']:.5f} (cost: ${buy_cost_with_fee * trade['amount']:.2f})")
        
        # Update database
        update_grid_order_status(level.buy_order_id, is_buy=True, filled_at=level.buy_filled_at)
        
        # Place paired sell order if not already placed
        if not level.sell_order_id:
            try:
                sell_order = exchange.create_order('sell', level.size, level.sell_price)
                level.sell_order_id = sell_order.get('id', f"sell_{level.level_index}")
                level.status = 'sell_placed'
                
                expected_profit = (level.sell_price * (1 - MAKER_FEE) - buy_cost_with_fee) * level.size
                log(f"  ✅ Paired Sell Placed L{level.level_index}: {level.size} @ {level.sell_price:.5f} (target profit: ${expected_profit:.4f})")
                
                # Update database with sell order ID
                save_grid_order(
                    self.grid_id, level.level_index,
                    level.buy_order_id, level.sell_order_id,
                    level.buy_price, level.sell_price,
                    level.size, level.status
                )
            except Exception as e:
                log(f"  ❌ Error placing paired sell order L{level.level_index}: {e}")
    
    def _handle_sell_fill(self, exchange, level: GridLevel, trade: dict) -> None:
        """Handle a sell order fill
        
        Args:
            exchange: HyperliquidExchange instance
            level: Grid level that was filled
            trade: Trade data
        """
        level.sell_filled_at = trade.get('timestamp', int(time.time() * 1000))
        level.status = 'completed'
        self.position -= trade['amount']
        
        # Calculate profit for this grid level
        sell_revenue_after_fee = trade['price'] * (1 - MAKER_FEE)
        buy_cost_with_fee = level.buy_price * (1 + MAKER_FEE)
        level.profit = (sell_revenue_after_fee - buy_cost_with_fee) * trade['amount']
        
        log(f"📉 Grid Sell Filled L{level.level_index}: {trade['amount']} @ {trade['price']:.5f}")
        log(f"   💰 Profit: ${level.profit:.4f} ({(level.profit / (buy_cost_with_fee * trade['amount']) * 100):.2f}%)")
        
        # Update database
        update_grid_order_status(level.sell_order_id, is_buy=False, 
                                filled_at=level.sell_filled_at, profit=level.profit)
        
        # ONLY place new buy order after sell completes (not immediately after buy fills)
        # Safety check: never buy above max price for stablecoins
        if level.buy_price > GRID_MAX_BUY_PRICE:
            log(f"  ⚠️ Not replacing buy L{level.level_index}: price {level.buy_price:.5f} > {GRID_MAX_BUY_PRICE:.5f}")
            level.status = 'completed'
            return
        
        try:
            buy_order = exchange.create_order('buy', level.size, level.buy_price)
            level.buy_order_id = buy_order.get('id', f"buy_{level.level_index}_new")
            level.sell_order_id = None
            level.status = 'buy_placed'
            level.buy_filled_at = None
            level.sell_filled_at = None
            
            log(f"  ✅ New Buy Placed L{level.level_index}: {level.size} @ {level.buy_price:.5f}")
            
            # Save new grid order
            save_grid_order(
                self.grid_id, level.level_index,
                level.buy_order_id, '',
                level.buy_price, level.sell_price,
                level.size, level.status
            )
        except Exception as e:
            log(f"  ❌ Error placing new buy order L{level.level_index}: {e}")
    
    def rebalance_grid(self, exchange, mid_price: float, usdc_balance: float) -> None:
        """Rebalance grid by canceling all orders and creating new grid
        
        Args:
            exchange: HyperliquidExchange instance
            mid_price: Current market mid price
            usdc_balance: Available USDC balance
        """
        log(f"🔄 Rebalancing grid...")
        
        # Cancel all existing orders
        try:
            exchange.cancel_all_orders()
            log(f"   ❌ Cancelled all existing orders")
            time.sleep(0.5)
        except Exception as e:
            log(f"   ⚠️ Error cancelling orders: {e}")
        
        # Deactivate old grid in database
        deactivate_grid(self.grid_id)
        
        # Show performance of old grid
        perf = get_grid_performance(self.grid_id)
        log(f"   📊 Old grid performance: {perf['completed_orders']} completed, ${perf['total_profit']:.2f} profit")
        
        # Create new grid
        self.grid_id = f"grid_{int(time.time())}"
        self.initialize_grid(mid_price)
        self.place_grid_orders(exchange, usdc_balance)
    
    def get_grid_status(self) -> dict:
        """Get current grid status
        
        Returns:
            dict: Grid status information
        """
        total_levels = len(self.grid_levels)
        buy_placed = sum(1 for l in self.grid_levels if l.status in ['buy_placed', 'buy_filled', 'sell_placed'])
        buy_filled = sum(1 for l in self.grid_levels if l.status in ['buy_filled', 'sell_placed'])
        completed = sum(1 for l in self.grid_levels if l.status == 'completed')
        total_profit = sum(l.profit for l in self.grid_levels if l.profit > 0)
        
        return {
            'grid_id': self.grid_id,
            'center_price': self.center_price,
            'total_levels': total_levels,
            'buy_placed': buy_placed,
            'buy_filled': buy_filled,
            'completed': completed,
            'position': self.position,
            'total_profit': total_profit
        }
