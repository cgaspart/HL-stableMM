#!/bin/bash

# Grid Trading Bot Startup Script
# Starts the grid trading bot with proper environment setup

echo "🔷 Starting Grid Trading Bot..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please create .env file with WALLET_ADDRESS and PRIVATE_KEY"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Check required environment variables
if [ -z "$WALLET_ADDRESS" ] || [ -z "$PRIVATE_KEY" ]; then
    echo "❌ Error: WALLET_ADDRESS and PRIVATE_KEY must be set in .env"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Check if required packages are installed
python3 -c "import ccxt" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Error: ccxt package not found"
    echo "Please install: pip install -r requirements.txt"
    exit 1
fi

# Run the grid trading bot
echo "🚀 Launching grid trading bot..."
python3 main_grid.py
