#!/bin/bash
# Start the RSLogger audio system

echo "Starting RSLogger Audio System..."

# Function to handle cleanup on exit
cleanup() {
    echo -e "\n\nShutting down audio system..."
    ./kill_all_audio.sh
    exit 0
}

# Set up trap for clean exit
trap cleanup EXIT INT TERM

# Start UI server in background
echo "Starting UI server on port 8080..."
python ws_ui_server.py --port 8080 &
UI_PID=$!

# Give UI server time to start
sleep 2

# Check if UI server is running
if ! ps -p $UI_PID > /dev/null; then
    echo "ERROR: UI server failed to start"
    exit 1
fi

echo "UI server started successfully (PID: $UI_PID)"
echo "Access the web interface at: http://localhost:8080"
echo ""
echo "You can now start recorder services in other terminals:"
echo "  python ws_recorder_service.py --id mic1"
echo "  python ws_recorder_service.py --id mic2 --device \"USB Audio\""
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for UI server to exit
wait $UI_PID