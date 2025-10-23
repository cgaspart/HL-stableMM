#!/bin/bash

echo "🎯 Starting Market Maker Dashboard..."
echo ""
echo "Make sure your bot (main.py) is running in another terminal!"
echo ""
echo "Dashboard will be available at: http://localhost:5000"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install dependencies if needed
pip install -q flask flask-cors

# Start the dashboard
python dashboard_api.py
