#!/bin/bash
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

# Start the Flask API in the background
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Flask API..."
python -u dashboard_api.py 2>&1 | sed 's/^/[API] /' &
API_PID=$!
echo "Flask API PID: $API_PID"

# Wait a few seconds for API to start
sleep 5

# Start the market maker bot
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Market Maker Bot..."
python -u main.py 2>&1 | sed 's/^/[BOT] /' &
BOT_PID=$!
echo "Market Maker Bot PID: $BOT_PID"

# Function to handle shutdown
shutdown() {
    echo ""
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Shutting down..."
    kill $API_PID $BOT_PID 2>/dev/null || true
    wait $API_PID $BOT_PID 2>/dev/null || true
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Shutdown complete"
    exit 0
}

# Trap SIGTERM and SIGINT
trap shutdown SIGTERM SIGINT

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Both processes started successfully"
echo "========================================="

# Wait for both processes and check if they exit
wait -n $API_PID $BOT_PID
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: One of the processes exited with code $EXIT_CODE"
    shutdown
fi
