"""
Stablecoin Market Maker Bot - Main Entry Point
Orchestrates the market making strategy using modular components
"""
import time
from config import (
    LOOP_INTERVAL, ORDER_SIZE, MAX_POSITION, TICK_SIZE, SELL_TRANCHES, 
    TRANCHE_SPREAD_BPS, INVENTORY_SKEW_THRESHOLD, ONLY_AVERAGE_DOWN, INCREMENTAL_SELL
)
from logger import log
from database import init_database, load_trades_from_db, save_position_snapshot, log_system_event
from exchange import HyperliquidExchange
from market_maker import MarketMaker
from order_manager import OrderManager


class StablecoinMarketMakerBot:
    """Main bot orchestrator"""
    
    def __init__(self):
        # Initialize components
        self.exchange = HyperliquidExchange()
        self.market_maker = MarketMaker()
        self.order_manager = OrderManager()
        
        # State tracking
        self.position = 0
        self.average_buy_price = 0
        self.processed_trade_ids = set()
        
        # Initialize database and load previous state
        init_database()
        self._load_position_from_db()
    
    def _load_position_from_db(self) -> None:
        """Reconstruct position and average buy price from database"""
        from config import MAKER_FEE
        
        trades = load_trades_from_db()
        
        if not trades:
            log("📊 No previous trades found in database")
            return
        
        # Reconstruct position and average
        calc_position = 0
        calc_avg = 0
        
        for trade_id, side, price, amount in trades:
            self.processed_trade_ids.add(trade_id)
            
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
        
        self.position = calc_position
        self.average_buy_price = calc_avg
        self.market_maker.update_position(self.position, self.average_buy_price)
        
        log(f"📊 Loaded from DB: {len(trades)} trades, Position: {self.position:.2f}, Avg: {self.average_buy_price:.5f}")
    
    def _update_position(self) -> tuple:
        """Update current position and USDC balance
        
        Returns:
            tuple: (position, usdc_balance)
        """
        position, usdc_balance = self.exchange.fetch_balance()
        
        # Sync position from exchange (source of truth)
        position_diff = abs(position - self.position)
        if position_diff > 0.1:
            log(f"🔄 Position sync: Exchange: {position:.2f}, Tracked: {self.position:.2f}, Diff: {position_diff:.2f}")
        
        self.position = position
        self.market_maker.update_position(self.position, self.average_buy_price)
        
        # Save snapshot periodically
        save_position_snapshot(self.position, self.average_buy_price, usdc_balance)
        
        # Log with average price if we have inventory
        if self.position > 0 and self.average_buy_price > 0:
            log(f"Position: {self.position:.2f} USDHL @ avg {self.average_buy_price:.5f} | USDC: {usdc_balance:.2f}")
        else:
            log(f"Position: {self.position:.2f} USDHL | USDC: {usdc_balance:.2f}")
        
        return self.position, usdc_balance
    
    def _check_filled_orders(self) -> None:
        """Check if any orders were filled and update average buy price"""
        from config import MAKER_FEE
        from database import save_trade_to_db
        
        trades = self.exchange.fetch_my_trades(limit=20)
        
        # Sort trades by timestamp (oldest first)
        trades_sorted = sorted(trades, key=lambda t: t.get('timestamp', 0))
        
        # Calculate position BEFORE new trades
        new_trade_position_delta = 0
        for trade in trades_sorted:
            trade_id = trade.get('id') or trade.get('order')
            if trade_id not in self.processed_trade_ids:
                if trade['side'] == 'buy':
                    new_trade_position_delta += trade['amount']
                elif trade['side'] == 'sell':
                    new_trade_position_delta -= trade['amount']
        
        calc_position = self.position - new_trade_position_delta
        calc_avg = self.average_buy_price
        
        # Process only new trades
        new_trades_found = False
        for trade in trades_sorted:
            trade_id = trade.get('id') or trade.get('order')
            
            if trade_id in self.processed_trade_ids:
                continue
            
            new_trades_found = True
            self.processed_trade_ids.add(trade_id)
            save_trade_to_db(trade)
            
            if trade['side'] == 'buy':
                price_with_fee = trade['price'] * (1 + MAKER_FEE)
                total_cost = calc_avg * calc_position + price_with_fee * trade['amount']
                calc_position += trade['amount']
                calc_avg = total_cost / calc_position if calc_position > 0 else 0
                
                log(f"📈 Buy filled: {trade['amount']} @ {trade['price']} (cost basis with fee: {price_with_fee:.5f}), New Avg: {calc_avg:.5f}")
            
            elif trade['side'] == 'sell':
                sell_revenue_after_fee = trade['price'] * (1 - MAKER_FEE)
                profit = (sell_revenue_after_fee - calc_avg) * trade['amount']
                
                log(f"📉 Sell filled: {trade['amount']} @ {trade['price']}, Net profit: ${profit:.4f}")
                
                calc_position -= trade['amount']
                
                if calc_position <= 5:
                    calc_avg = 0
                    log(f"🔄 Position cleared, resetting average")
        
        if new_trades_found:
            self.average_buy_price = calc_avg
            self.market_maker.update_position(self.position, self.average_buy_price)
        
        # Prevent memory bloat
        if len(self.processed_trade_ids) > 100:
            self.processed_trade_ids = set(list(self.processed_trade_ids)[-50:])
    
    def _run_iteration(self) -> None:
        """Run a single market making iteration"""
        # Update position and get USDC balance
        position, usdc_balance = self._update_position()
        
        # Check for filled orders
        self._check_filled_orders()
        
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
        
        # Calculate orderbook depth (top 5 levels)
        bid_depth = sum([level[1] for level in orderbook['bids'][:5]]) if len(orderbook['bids']) >= 5 else 0
        ask_depth = sum([level[1] for level in orderbook['asks'][:5]]) if len(orderbook['asks']) >= 5 else 0
        
        # Save market snapshot
        from database import save_market_snapshot
        save_market_snapshot(mid_price, highest_bid, lowest_ask, spread_bps, bid_depth, ask_depth)
        
        # Check if we need to requote
        need_requote, reason = self.order_manager.should_requote(highest_bid, lowest_ask, position)
        
        if need_requote:
            log(f"🔄 Requoting: {reason}")
            log(f"📊 Market: Bid={highest_bid:.5f}, Ask={lowest_ask:.5f}, Mid={mid_price:.5f}, Spread={spread_bps:.1f} bps")
            
            # Cancel existing orders
            self.exchange.cancel_all_orders()
            time.sleep(0.3)
            
            # Calculate order prices and sizes
            bid_price, ask_price = self.market_maker.calculate_order_prices(
                mid_price, lowest_ask, highest_bid, spread_bps
            )
            buy_size, sell_size = self.market_maker.calculate_order_sizes()
            
            # Calculate sell tranches
            sell_tranches = self.market_maker.calculate_sell_tranches(ask_price) if ask_price else []
            
            # Place orders
            orders = self.order_manager.place_orders(
                self.exchange, bid_price, ask_price, usdc_balance,
                position, self.average_buy_price, buy_size, sell_size, sell_tranches
            )
            
            # Update order tracking
            self.order_manager.update_order_state(highest_bid, lowest_ask, position)
            
            # Wait for potential fills
            if len(orders) > 0:
                time.sleep(1)
        else:
            log(f"⏸️ Keeping orders: Market stable (bid={highest_bid:.5f}, ask={lowest_ask:.5f})")
    
    def run(self) -> None:
        """Main bot loop"""
        log("🚀 Starting stablecoin market making bot...")
        log(f"Configuration: OrderSize={ORDER_SIZE}, MaxPos={MAX_POSITION}, TickSize={TICK_SIZE}")
        log(f"Strategy: MinSpread=3bps, Tranches={SELL_TRANCHES}, InventorySkew={INVENTORY_SKEW_THRESHOLD*100:.0f}%")
        if ONLY_AVERAGE_DOWN:
            log("⚠️ ONLY_AVERAGE_DOWN ENABLED: Bot will only buy when price (with fees) is below current average")
        if INCREMENTAL_SELL:
            log(f"✅ INCREMENTAL_SELL ENABLED: Selling in {SELL_TRANCHES} tranches with {TRANCHE_SPREAD_BPS}bps spacing")
        
        try:
            while True:
                try:
                    self._run_iteration()
                    time.sleep(LOOP_INTERVAL)
                except KeyboardInterrupt:
                    log("⚠️ Keyboard interrupt received")
                    raise
                except Exception as e:
                    log(f"❌ Error in main loop: {e}")
                    time.sleep(LOOP_INTERVAL)
        
        except KeyboardInterrupt:
            log("🛑 Shutting down bot...")
            self.exchange.cancel_all_orders()
            log("✅ All orders cancelled. Bot stopped.")


if __name__ == "__main__":
    bot = StablecoinMarketMakerBot()
    bot.run()
