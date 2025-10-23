#!/bin/bash

# Set database path to volume
export DB_PATH=${DB_PATH:-/app/data/market_maker.db}

# Create a symbolic link to the database in the volume
ln -sf $DB_PATH /app/market_maker.db

echo "Starting Hyperliquid Market Maker..."
echo "Database location: $DB_PATH"

# Start the Flask API in the background
echo "Starting Flask API..."
python dashboard_api.py &
API_PID=$!

# Wait a few seconds for API to start
sleep 5

# Start the market maker bot
echo "Starting Market Maker Bot..."
python main.py &
BOT_PID=$!

# Function to handle shutdown
shutdown() {
    echo "Shutting down..."
    kill $API_PID $BOT_PID
    wait $API_PID $BOT_PID
    exit 0
}

# Trap SIGTERM and SIGINT
trap shutdown SIGTERM SIGINT

# Wait for both processes
wait $API_PID $BOT_PID
