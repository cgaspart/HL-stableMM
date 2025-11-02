"""
Configuration module for stablecoin market maker bot
Centralized place for all parameters and settings
"""
import os

# ============================================================================
# EXCHANGE CONFIGURATION
# ============================================================================
WALLET_ADDRESS = os.getenv('WALLET_ADDRESS')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
USDHL_MARKET_PAIR = 'USDHL/USDC'

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
DB_PATH = os.getenv('DB_PATH', 'market_maker.db')

# ============================================================================
# MARKET MAKING PARAMETERS
# ============================================================================
MAKER_FEE = 0.0004  # 0.04% maker fee for Hyperliquid spot

# Order sizing
ORDER_SIZE = 50  # Base size in USDHL per order
MAX_POSITION = 500  # Maximum inventory in USDHL
LOOP_INTERVAL = 3  # seconds between iterations

# Price precision
TICK_SIZE = 0.00001  # Minimum price increment for USDHL/USDC

# Inventory management
SKEW_FACTOR = 2.0  # Multiplier for order size adjustment based on inventory
TARGET_INVENTORY = 0  # Target neutral inventory

# ============================================================================
# STABLECOIN MM STRATEGY PARAMETERS
# ============================================================================
MIN_SPREAD_BPS = 3  # Minimum spread in basis points (0.03%) to trade
ONLY_AVERAGE_DOWN = True  # Set to False to allow buying at any price

# Incremental selling
INCREMENTAL_SELL = True  # Sell in tranches instead of all at once
SELL_TRANCHES = 4  # Number of sell levels (25% each)
TRANCHE_SPREAD_BPS = 2  # Additional spread per tranche in bps (0.02%)

# Inventory skewing
INVENTORY_SKEW_THRESHOLD = 0.6  # At 60% of max position, start aggressive skewing
AVERAGE_DOWN_THRESHOLD_BPS = 5  # Only average down when high inventory if price is 20+ bps below average

# ============================================================================
# SMART ORDER MANAGEMENT
# ============================================================================
REQUOTE_THRESHOLD_TICKS = 2  # Only requote if price moves >2 ticks
REQUOTE_ON_POSITION_CHANGE = True  # Requote when position changes
MAX_ORDER_AGE_SECONDS = 120  # Force requote after this time

# ============================================================================
# YIELD FARMING PARAMETERS (for future use)
# ============================================================================
ENABLE_YIELD_FARMING = False  # Enable EVM yield farming
YIELD_FARMING_THRESHOLD = 100  # Minimum position to transfer to yield farm
EVM_CHAIN_ID = 1  # Ethereum mainnet
EVM_LENDING_PROTOCOL = "aave"  # Lending protocol to use

# ============================================================================
# DYNAMIC ALLOCATION PARAMETERS (for future use)
# ============================================================================
ENABLE_DYNAMIC_ALLOCATION = False  # Enable dynamic allocation between strategies
ALLOCATION_REBALANCE_INTERVAL = 3600  # Rebalance every hour (seconds)
ALLOCATION_MIN_POSITION = 50  # Minimum position to consider for allocation

# ============================================================================
# GRID TRADING PARAMETERS
# ============================================================================
# Grid structure
GRID_LEVELS = 10  # Number of grid levels (buy/sell pairs)
GRID_SIZE = 50  # USDHL per grid level
GRID_SPACING_BPS = 5  # Distance between grid levels in bps (0.05%)
PROFIT_TARGET_BPS = 10  # Profit target per round-trip in bps (0.10%)

# Grid management
MAX_GRID_POSITION = 500  # Maximum total inventory across all grids
GRID_REBALANCE_THRESHOLD_BPS = 50  # Recreate grid if price moves >50 bps from center (0.5%)
GRID_CHECK_INTERVAL = 2  # Seconds between grid checks

# Grid order placement
GRID_MIN_ORDER_VALUE = 10.0  # Minimum order value in USDC
GRID_PLACE_BOTH_SIDES = True  # Place both buy and sell orders initially (False = only buys)
GRID_MAX_BUY_PRICE = 0.9999  # Never buy above this price (stablecoin peg protection)
