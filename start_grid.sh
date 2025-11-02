#!/bin/bash

# Grid Trading Bot Startup Script
# Starts the grid trading bot with proper environment setup

set -e

# Set database path to volume
export DB_PATH=${DB_PATH:-/app/data/market_maker.db}

# Create a symbolic link to the database in the volume
ln -sf $DB_PATH /app/market_maker.db

echo "========================================="
echo "Starting Hyperliquid Market Maker"
echo "========================================="
echo "Database location: $DB_PATH"
echo "Python version: $(python --version)"
echo "========================================="

echo "🔷 Starting Grid Trading Bot..."


echo "🚀 Launching grid trading bot..."
python3 main_grid.py
