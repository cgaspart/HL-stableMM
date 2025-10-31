"""
Order management module
Handles order placement, cancellation, and lifecycle tracking
"""
import time
from config import MAKER_FEE, MAX_POSITION, TICK_SIZE, REQUOTE_THRESHOLD_TICKS, REQUOTE_ON_POSITION_CHANGE, MAX_ORDER_AGE_SECONDS
from logger import log
from database import log_order_event, log_system_event


class OrderManager:
    """Manages order placement, cancellation, and tracking"""
    
    def __init__(self):
        self.active_orders = []
        self.last_bid_price = None
        self.last_ask_price = None
        self.last_position = 0
        self.last_orderbook_update = 0
    
    def should_requote(self, current_bid: float, current_ask: float, current_position: float) -> tuple:
        """Determine if we should cancel and replace orders
        
        Args:
            current_bid: Current best bid
            current_ask: Current best ask
            current_position: Current position
            
        Returns:
            tuple: (should_requote: bool, reason: str)
        """
        # First time or no previous orders
        if self.last_bid_price is None or self.last_ask_price is None:
            return True, "Initial order placement"
        
        # Check if position changed (fill detected)
        if REQUOTE_ON_POSITION_CHANGE and abs(current_position - self.last_position) > 0.1:
            return True, f"Position changed: {self.last_position:.2f} -> {current_position:.2f}"
        
        # Check if prices moved beyond threshold
        bid_moved = abs(current_bid - self.last_bid_price) if current_bid and self.last_bid_price else 0
        ask_moved = abs(current_ask - self.last_ask_price) if current_ask and self.last_ask_price else 0
        price_threshold = REQUOTE_THRESHOLD_TICKS * TICK_SIZE
        
        if bid_moved > price_threshold or ask_moved > price_threshold:
            return True, f"Price moved: bid {bid_moved/TICK_SIZE:.0f} ticks, ask {ask_moved/TICK_SIZE:.0f} ticks"
        
        # Check if orders are too old
        order_age = time.time() - self.last_orderbook_update
        if order_age > MAX_ORDER_AGE_SECONDS:
            return True, f"Orders aged out ({order_age:.0f}s > {MAX_ORDER_AGE_SECONDS}s)"
        
        return False, "No requote needed"
    
    def update_order_state(self, highest_bid: float, lowest_ask: float, position: float) -> None:
        """Update order tracking state after placing orders
        
        Args:
            highest_bid: Best bid price
            lowest_ask: Best ask price
            position: Current position
        """
        self.last_bid_price = highest_bid
        self.last_ask_price = lowest_ask
        self.last_position = position
        self.last_orderbook_update = time.time()
    
    def place_orders(self, exchange, bid_price: float, ask_price: float, 
                    usdc_balance: float, position: float, average_buy_price: float,
                    buy_size: float, sell_size: float, sell_tranches: list) -> list:
        """Place buy and sell limit orders with dynamic sizing
        
        Args:
            exchange: HyperliquidExchange instance
            bid_price: Bid price (can be None)
            ask_price: Ask price (can be None)
            usdc_balance: Available USDC
            position: Current position
            average_buy_price: Average buy price
            buy_size: Size for buy order
            sell_size: Size for sell order
            sell_tranches: List of (price, size, index, bps) tuples for sell tranches
            
        Returns:
            list: List of placed orders
        """
        orders_placed = []
        
        # If both prices are None, skip order placement
        if bid_price is None and ask_price is None:
            log("⏸️ No orders to place this cycle")
            return orders_placed
        
        # Calculate how much USDC we need for the buy order
        usdc_needed = buy_size * bid_price if bid_price else 0
        
        # Ensure minimum order value of 10 USDC for buy orders
        MIN_BUY_VALUE_USDC = 10.0
        if bid_price and usdc_needed < MIN_BUY_VALUE_USDC:
            buy_size = 11
            usdc_needed = 11 * bid_price
            log(f"📊 Adjusted buy size to {buy_size:.3f} to meet minimum order value of {MIN_BUY_VALUE_USDC} USDC")
        
        # Place buy order if we have enough USDC and haven't hit max position
        should_buy = True
        if bid_price and position > 0 and average_buy_price > 0:
            # Calculate what the buy price would be WITH fees included
            buy_price_with_fee = bid_price * (1 + MAKER_FEE)
            
            # Only buy if it would lower our average (if enabled)
            from config import ONLY_AVERAGE_DOWN
            if ONLY_AVERAGE_DOWN and buy_price_with_fee >= average_buy_price:
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
                    order = exchange.create_order('buy', buy_size, bid_price)
                    orders_placed.append(order)
                    log_order_event(order.get('id', 'unknown'), 'placed', 'buy', bid_price, buy_size, f"Cost: {usdc_needed:.2f} USDC")
                    log(f"✅ BUY order placed: {buy_size} @ {bid_price} (Cost: {usdc_needed:.2f} USDC)")
                except Exception as e:
                    log(f"❌ Error placing buy order: {e}")
        elif position >= MAX_POSITION:
            log(f"⚠️ Max position reached ({position:.2f}/{MAX_POSITION})")
        elif usdc_balance < usdc_needed:
            log(f"⚠️ Insufficient USDC: have {usdc_balance:.2f}, need {usdc_needed:.2f}")
        
        # Place sell orders
        if ask_price and position > 0:
            min_order_value = 10.0
            
            if sell_tranches:
                # Sell in multiple tranches
                for tranche_price, tranche_size, tranche_idx, price_improvement_bps in sell_tranches:
                    order_value = tranche_size * tranche_price
                    
                    if order_value >= min_order_value and tranche_size >= 1:
                        try:
                            order = exchange.create_order('sell', tranche_size, tranche_price)
                            orders_placed.append(order)
                            
                            sell_revenue_after_fee = tranche_price * (1 - MAKER_FEE)
                            expected_profit = (sell_revenue_after_fee - average_buy_price) * tranche_size
                            
                            log_order_event(order.get('id', 'unknown'), 'placed', 'sell', tranche_price, tranche_size, 
                                           f"Tranche {tranche_idx+1}, +{price_improvement_bps} bps, profit: ${expected_profit:.4f}")
                            log(f"✅ SELL tranche {tranche_idx+1}: {tranche_size} @ {tranche_price:.5f} (+{price_improvement_bps} bps, profit: ${expected_profit:.4f})")
                        except Exception as e:
                            log(f"❌ Error placing sell tranche {tranche_idx+1}: {e}")
            else:
                # Single sell order
                actual_sell_size = round(position * 0.99, 3)
                order_value = actual_sell_size * ask_price
                
                if order_value >= min_order_value and actual_sell_size >= 1:
                    try:
                        order = exchange.create_order('sell', actual_sell_size, ask_price)
                        orders_placed.append(order)
                        
                        sell_revenue_after_fee = ask_price * (1 - MAKER_FEE)
                        expected_profit = (sell_revenue_after_fee - average_buy_price) * actual_sell_size
                        
                        log_order_event(order.get('id', 'unknown'), 'placed', 'sell', ask_price, actual_sell_size, 
                                       f"Profit: ${expected_profit:.4f}, Avg: {average_buy_price:.5f}")
                        log(f"✅ SELL order placed: {actual_sell_size} @ {ask_price} (Profit: ${expected_profit:.4f}, Avg: {average_buy_price:.5f})")
                    except Exception as e:
                        log(f"❌ Error placing sell order: {e}")
        
        self.active_orders = orders_placed
        return orders_placed
