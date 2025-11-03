"""
Grid Trading Bot - Main Entry Point
Runs independent grid trading strategy for stablecoin market making
Each grid level operates independently with its own P&L
"""
import time
from config import (
    GRID_CHECK_INTERVAL, GRID_LEVELS, GRID_SIZE, GRID_SPACING_BPS,
    PROFIT_TARGET_BPS, MAX_GRID_POSITION, GRID_REBALANCE_THRESHOLD_BPS
)
from logger import log
from database import init_database, save_position_snapshot, log_system_event
from exchange import HyperliquidExchange
from grid_strategy import GridStrategy


class GridTradingBot:
    """Main bot orchestrator for grid trading"""
    
    def __init__(self):
        # Initialize components
        self.exchange = HyperliquidExchange()
        self.grid = GridStrategy()
        
        # Initialize database
        init_database()
        
        log("🔷 Grid Trading Bot initialized")
    
    def _update_position(self) -> tuple:
        """Update current position and USDC balance
        
        Returns:
            tuple: (position, usdc_balance)
        """
        position, usdc_balance = self.exchange.fetch_balance()
        
        # Sync position with grid strategy
        position_diff = abs(position - self.grid.position)
        if position_diff > 0.1:
            log(f"🔄 Position sync: Exchange: {position:.2f}, Grid: {self.grid.position:.2f}, Diff: {position_diff:.2f}")
            self.grid.position = position
        
        # Save snapshot
        save_position_snapshot(position, 0, usdc_balance)  # No average price in grid strategy
        
        log(f"Position: {position:.2f} USDHL | USDC: {usdc_balance:.2f}")
        
        return position, usdc_balance
    
    def _run_iteration(self) -> None:
        """Run a single grid trading iteration"""
        # Update position and balance
        position, usdc_balance = self._update_position()
        
        # Check for filled orders
        self.grid.check_filled_orders(self.exchange)
        
        # Fetch current orderbook
        orderbook = self.exchange.fetch_orderbook()
        lowest_ask = orderbook['asks'][0][0] if orderbook['asks'] else None
        highest_bid = orderbook['bids'][0][0] if orderbook['bids'] else None
        
        if not lowest_ask or not highest_bid:
            log("⚠️ Incomplete orderbook, skipping iteration")
            return
        
        mid_price = (lowest_ask + highest_bid) / 2
        spread_pct = ((lowest_ask - highest_bid) / mid_price) * 100
        spread_bps = spread_pct * 100
        
        log(f"📊 Market: Bid={highest_bid:.5f}, Ask={lowest_ask:.5f}, Mid={mid_price:.5f}, Spread={spread_bps:.1f} bps")
        
        # Check if grid needs initialization or rebalancing
        if not self.grid.grid_levels:
            log("🆕 No active grid, initializing...")
            self.grid.initialize_grid(mid_price)
            self.grid.place_grid_orders(self.exchange, usdc_balance)
        elif self.grid.should_rebalance_grid(mid_price):
            self.grid.rebalance_grid(self.exchange, mid_price, usdc_balance)
        else:
            # Check if any levels need orders placed
            orders_needed = self.grid.check_and_place_missing_orders(self.exchange, usdc_balance)
            
            # Show grid status
            status = self.grid.get_grid_status()
            if orders_needed > 0:
                log(f"📊 Grid Status: {status['buy_filled']}/{status['total_levels']} filled, "
                    f"{status['completed']} completed, ${status['total_profit']:.2f} profit, {orders_needed} orders placed")
            else:
                log(f"📊 Grid Status: {status['buy_filled']}/{status['total_levels']} filled, "
                    f"{status['completed']} completed, ${status['total_profit']:.2f} profit")
    
    def run(self) -> None:
        """Main bot loop"""
        log("🚀 Starting Grid Trading Bot...")
        log(f"Configuration:")
        log(f"  Levels: {GRID_LEVELS}, Size: {GRID_SIZE} USDHL per level")
        log(f"  Spacing: {GRID_SPACING_BPS} bps, Profit Target: {PROFIT_TARGET_BPS} bps")
        log(f"  Max Position: {MAX_GRID_POSITION} USDHL")
        log(f"  Rebalance Threshold: {GRID_REBALANCE_THRESHOLD_BPS} bps")
        
        log_system_event('bot_start', 'info', 'Grid Trading Bot started', 
                        f"Levels={GRID_LEVELS}, Size={GRID_SIZE}, Spacing={GRID_SPACING_BPS}bps")
        
        try:
            while True:
                try:
                    self._run_iteration()
                    time.sleep(GRID_CHECK_INTERVAL)
                except KeyboardInterrupt:
                    log("⚠️ Keyboard interrupt received")
                    raise
                except Exception as e:
                    log(f"❌ Error in main loop: {e}")
                    import traceback
                    log(traceback.format_exc())
                    time.sleep(GRID_CHECK_INTERVAL)
        
        except KeyboardInterrupt:
            log("🛑 Shutting down Grid Trading Bot...")
            
            # Show final performance
            status = self.grid.get_grid_status()
            log(f"📊 Final Grid Performance:")
            log(f"   Total Levels: {status['total_levels']}")
            log(f"   Completed Cycles: {status['completed']}")
            log(f"   Total Profit: ${status['total_profit']:.2f}")
            log(f"   Final Position: {status['position']:.2f} USDHL")
            
            # Cancel all orders
            self.exchange.cancel_all_orders()
            log("✅ All orders cancelled. Bot stopped.")
            
            log_system_event('bot_stop', 'info', 'Grid Trading Bot stopped', 
                           f"Profit=${status['total_profit']:.2f}, Position={status['position']:.2f}")


if __name__ == "__main__":
    bot = GridTradingBot()
    bot.run()
