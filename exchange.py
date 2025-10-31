"""
Exchange module for Hyperliquid interactions
Handles position tracking, balance updates, and market data fetching
"""
import ccxt
import os
from config import WALLET_ADDRESS, PRIVATE_KEY, USDHL_MARKET_PAIR
from logger import log
from database import save_position_snapshot


class HyperliquidExchange:
    """Wrapper for Hyperliquid exchange operations"""
    
    def __init__(self):
        self.exchange = ccxt.hyperliquid({
            'walletAddress': WALLET_ADDRESS,
            'privateKey': PRIVATE_KEY,
            'enableRateLimit': True,
        })
        self.market_id = self._find_market_id()
        if not self.market_id:
            raise Exception("USDHL market not found")
    
    def _find_market_id(self) -> str:
        """Find USDHL/USDC market ID"""
        markets = self.exchange.fetchMarkets()
        for market in markets:
            if market['spot'] and market['base'] == "USDHL":
                log(f"Found market: {market['id']}")
                return market['id']
        return None
    
    def get_market_id(self) -> str:
        """Get the market ID for USDHL/USDC"""
        return self.market_id
    
    def fetch_balance(self) -> tuple:
        """Fetch current balance and position
        
        Returns:
            tuple: (position_usdhl, usdc_balance)
        """
        try:
            balance = self.exchange.fetch_balance({'type': 'spot'})
            position = balance.get('USDHL', {}).get('total', 0)
            usdc_balance = balance.get('USDC', {}).get('free', 0)
            return position, usdc_balance
        except Exception as e:
            log(f"Error fetching balance: {e}")
            return 0, 0
    
    def fetch_orderbook(self) -> dict:
        """Fetch current orderbook
        
        Returns:
            dict: Orderbook with 'bids' and 'asks' keys
        """
        try:
            return self.exchange.fetchOrderBook(self.market_id)
        except Exception as e:
            log(f"Error fetching orderbook: {e}")
            return {'bids': [], 'asks': []}
    
    def fetch_my_trades(self, limit: int = 20) -> list:
        """Fetch recent trades for this account
        
        Args:
            limit: Number of recent trades to fetch
            
        Returns:
            list: List of trade dictionaries
        """
        try:
            return self.exchange.fetchMyTrades(self.market_id, limit=limit)
        except Exception as e:
            log(f"Error fetching trades: {e}")
            return []
    
    def fetch_open_orders(self) -> list:
        """Fetch all open orders
        
        Returns:
            list: List of open order dictionaries
        """
        try:
            return self.exchange.fetchOpenOrders(self.market_id)
        except Exception as e:
            log(f"Error fetching open orders: {e}")
            return []
    
    def create_order(self, side: str, size: float, price: float) -> dict:
        """Create a limit order
        
        Args:
            side: 'buy' or 'sell'
            size: Order size in USDHL
            price: Limit price
            
        Returns:
            dict: Order response
        """
        try:
            params = {'vaultAddress': None}  # Use wallet, not vault for spot
            order = self.exchange.create_order(
                USDHL_MARKET_PAIR,
                'limit',
                side,
                size,
                price,
                params
            )
            return order
        except Exception as e:
            log(f"Error creating {side} order: {e}")
            raise
    
    def cancel_order(self, order_id: str) -> None:
        """Cancel an order
        
        Args:
            order_id: Order ID to cancel
        """
        try:
            self.exchange.cancelOrder(order_id, self.market_id)
        except Exception as e:
            log(f"Error cancelling order {order_id}: {e}")
            raise
    
    def cancel_all_orders(self) -> None:
        """Cancel all open orders"""
        try:
            open_orders = self.fetch_open_orders()
            for order in open_orders:
                try:
                    self.cancel_order(order['id'])
                    log(f"❌ Cancelled order {order['id']}")
                except Exception as e:
                    log(f"Error cancelling order {order['id']}: {e}")
        except Exception as e:
            log(f"Error fetching/cancelling orders: {e}")
