#!/bin/bash
# Kill all RSLogger audio processes

echo "Stopping all RSLogger audio processes..."

# Kill WebSocket UI servers
echo "Stopping UI servers..."
pkill -f "ws_ui_server.py" 2>/dev/null

# Kill recorder services
echo "Stopping recorder services..."
pkill -f "ws_recorder_service.py" 2>/dev/null

# Kill any main.py processes
echo "Stopping main processes..."
pkill -f "main.py" 2>/dev/null

# Kill any Python processes using sounddevice (more aggressive)
echo "Stopping any remaining audio processes..."
pkill -f "python.*sounddevice" 2>/dev/null

# Give processes time to clean up
sleep 1

# Force kill if any are still running
echo "Force stopping any stubborn processes..."
pkill -9 -f "ws_ui_server.py" 2>/dev/null
pkill -9 -f "ws_recorder_service.py" 2>/dev/null

echo "All RSLogger processes terminated."

# Show any remaining Python processes (for debugging)
echo ""
echo "Remaining Python processes:"
ps aux | grep python | grep -v grep | grep -E "(ws_|main\.py)" || echo "None found."