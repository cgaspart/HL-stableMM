"""
Market making strategy module
Contains core logic for order pricing, sizing, and inventory management
"""
from config import (
    MAKER_FEE, ORDER_SIZE, MAX_POSITION, TICK_SIZE, SKEW_FACTOR, TARGET_INVENTORY,
    MIN_SPREAD_BPS, ONLY_AVERAGE_DOWN, INCREMENTAL_SELL, SELL_TRANCHES, 
    TRANCHE_SPREAD_BPS, INVENTORY_SKEW_THRESHOLD, AVERAGE_DOWN_THRESHOLD_BPS
)
from logger import log
from database import log_system_event


class MarketMaker:
    """Core market making strategy"""
    
    def __init__(self, position: float = 0, average_buy_price: float = 0):
        self.position = position
        self.average_buy_price = average_buy_price
    
    def update_position(self, position: float, average_buy_price: float) -> None:
        """Update current position and average buy price"""
        self.position = position
        self.average_buy_price = average_buy_price
    
    def calculate_order_sizes(self) -> tuple:
        """Calculate buy and sell order sizes based on inventory skew
        
        Returns:
            tuple: (buy_size, sell_size)
        """
        # Calculate inventory ratio: -1 (max short) to +1 (max long)
        inventory_ratio = self.position / MAX_POSITION if MAX_POSITION > 0 else 0
        inventory_ratio = max(-1, min(1, inventory_ratio))  # Clamp to [-1, 1]
        
        # Skew sizes: more inventory = larger sells, smaller buys
        buy_skew = 1 - (inventory_ratio * SKEW_FACTOR * 0.5)  # Reduce buys when long
        sell_skew = 1 + (inventory_ratio * SKEW_FACTOR * 0.5)  # Increase sells when long
        
        buy_size = ORDER_SIZE * max(0.2, buy_skew)  # Min 20% of base size
        sell_size = ORDER_SIZE * max(0.2, sell_skew)  # Min 20% of base size
        
        return round(buy_size, 3), round(sell_size, 3)
    
    def calculate_order_prices(self, mid_price: float, lowest_ask: float, 
                              highest_bid: float, spread_bps: float) -> tuple:
        """Calculate bid and ask prices - stablecoin MM strategy
        
        Args:
            mid_price: Mid price of the market
            lowest_ask: Best ask price
            highest_bid: Best bid price
            spread_bps: Spread in basis points
            
        Returns:
            tuple: (bid_price, ask_price) - either can be None if not trading
        """
        # Calculate inventory ratio for skewing
        inventory_ratio = (self.position - TARGET_INVENTORY) / MAX_POSITION if MAX_POSITION > 0 else 0
        
        # Initialize prices
        bid_price = highest_bid
        ask_price = lowest_ask
        
        # Check if we can do inventory management actions (bypass spread check)
        can_average_down = False
        can_sell_profit = False
        
        if self.position > 0 and self.average_buy_price > 0:
            # Check if we can average down
            buy_price_with_fee = highest_bid * (1 + MAKER_FEE)
            can_average_down = buy_price_with_fee < self.average_buy_price
            
            # Check if we can sell at profit
            breakeven_price = self.average_buy_price / (1 - MAKER_FEE)
            can_sell_profit = lowest_ask >= breakeven_price
        
        # Only enforce MIN_SPREAD_BPS if we're NOT doing inventory management
        if spread_bps < MIN_SPREAD_BPS:
            if can_average_down or can_sell_profit:
                log(f"⚡ Spread tight ({spread_bps:.2f} bps) but inventory management available:")
                log_system_event('spread_check', 'warning', 
                               f"Spread tight ({spread_bps:.2f} bps) but inventory management available",
                               f"can_average_down={can_average_down}, can_sell_profit={can_sell_profit}")
                if can_average_down:
                    log(f"   ✅ Can average down: {highest_bid:.5f} < avg {self.average_buy_price:.5f}")
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
                
                if can_average_down and self.average_buy_price > 0:
                    # Calculate how much better the price is (in bps)
                    buy_price_with_fee = bid_price * (1 + MAKER_FEE) if bid_price else highest_bid * (1 + MAKER_FEE)
                    price_improvement_bps = ((self.average_buy_price - buy_price_with_fee) / self.average_buy_price) * 10000
                    
                    if price_improvement_bps >= AVERAGE_DOWN_THRESHOLD_BPS:
                        should_block_buy = False
                        log(f"⚡ High inventory ({self.position:.2f}) but price {price_improvement_bps:.1f} bps below avg - allowing buy")
                        log_system_event('inventory_management', 'warning', 
                                       f"High inventory ({self.position:.2f}) but allowing buy - price {price_improvement_bps:.1f} bps below avg", '')
                    else:
                        log(f"⚠️ High inventory ({self.position:.2f}), price improvement {price_improvement_bps:.1f} bps < threshold {AVERAGE_DOWN_THRESHOLD_BPS} bps")
                
                if should_block_buy:
                    log(f"⚠️ High inventory ({self.position:.2f}), only placing sell orders")
                    log_system_event('inventory_management', 'warning', 
                                   f"High inventory ({self.position:.2f}/{MAX_POSITION}) - Blocking buys, only selling", '')
                    bid_price = None
        
        # Only place sell if we have inventory and it's profitable
        if ask_price and self.position > 0 and self.average_buy_price > 0:
            breakeven_price = self.average_buy_price / (1 - MAKER_FEE)
            
            if ask_price >= breakeven_price:
                # Profitable - can sell
                profit_per_unit = ask_price * (1 - MAKER_FEE) - self.average_buy_price
                total_profit = profit_per_unit * self.position
                log(f"💰 Profitable sell opportunity: ask={ask_price:.5f} >= breakeven={breakeven_price:.5f}, profit=${total_profit:.2f}")
                log_system_event('sell_decision', 'info', 
                               f"Profitable sell: ask={ask_price:.5f} >= breakeven={breakeven_price:.5f}", 
                               f"Expected profit: ${total_profit:.2f}")
            else:
                # Not profitable yet - only place buy to average down
                log(f"⏸️ Waiting for profit: ask={ask_price:.5f} < breakeven={breakeven_price:.5f} (avg={self.average_buy_price:.5f})")
                log_system_event('sell_decision', 'info', 
                               f"Waiting for profit: ask={ask_price:.5f} < breakeven={breakeven_price:.5f}", '')
                ask_price = None
        
        return round(bid_price, 5) if bid_price else None, round(ask_price, 5) if ask_price else None
    
    def calculate_sell_tranches(self, ask_price: float) -> list:
        """Calculate sell order tranches for incremental selling
        
        Args:
            ask_price: Base ask price
            
        Returns:
            list: List of (price, size) tuples for each tranche
        """
        tranches = []
        
        if not INCREMENTAL_SELL or self.position <= 50:
            # Small position - sell all at once
            return [(ask_price, round(self.position * 0.99, 3), 0, 0)]
        
        # Sell in multiple tranches at different price levels
        breakeven_price = self.average_buy_price / (1 - MAKER_FEE)
        base_tranche_size = round(self.position / SELL_TRANCHES, 3)
        total_allocated = 0
        
        log(f"📊 Incremental selling: {SELL_TRANCHES} tranches of ~{base_tranche_size:.2f} USDHL each")
        
        for i in range(SELL_TRANCHES):
            # Each tranche at progressively better prices
            price_improvement_bps = i * TRANCHE_SPREAD_BPS
            tranche_price = ask_price * (1 + price_improvement_bps / 10000)
            
            # Ensure we're still profitable
            if tranche_price < breakeven_price:
                continue
            
            # Last tranche gets any remainder
            if i == SELL_TRANCHES - 1:
                tranche_size = round((self.position * 0.99) - total_allocated, 3)
            else:
                tranche_size = base_tranche_size
            
            total_allocated += tranche_size
            
            if tranche_size >= 1:
                tranches.append((round(tranche_price, 5), tranche_size, i, price_improvement_bps))
        
        return tranches
