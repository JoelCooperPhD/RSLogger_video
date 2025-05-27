# RSLogger Web UI

Modern web-based user interface for RSLogger, providing browser-based control and monitoring of research devices.

## Overview

This module provides two web UI server implementations:
- **WebSocket Server** (`ws_ui_server.py`): Real-time bidirectional communication
- **MQTT Server** (`mqtt_ui_server.py`): Distributed messaging for multi-client scenarios

Both servers provide the same web interface but use different communication protocols.

## Features

- Real-time device status monitoring
- Start/stop/pause recording controls
- Multi-device support
- Responsive web design
- WebSocket or MQTT communication options
- Integration with RSLogger's hardware interfaces

## Architecture

```
RSLogger/
├── web_ui/
│   ├── __init__.py
│   ├── mqtt_ui_server.py      # MQTT-based server
│   ├── ws_ui_server.py        # WebSocket-based server
│   ├── rslogger_integration.py # Bridge to RSLogger architecture
│   ├── test_recording.html    # Simple test interface
│   └── static/               # Web assets
│       ├── index.html        # Main UI
│       ├── styles.css        # Styling
│       └── app.js           # Client-side logic
```

## Usage

### Standalone WebSocket Server

```bash
cd RSLogger/web_ui
python ws_ui_server.py --port 8000
```

### Standalone MQTT Server

```bash
cd RSLogger/web_ui
python mqtt_ui_server.py --broker localhost --port 8000
```

### Integration with RSLogger

```python
from web_ui.rslogger_integration import create_web_ui_launcher

# Create launcher with RSLogger's queues
launcher = create_web_ui_launcher(
    hardware_queue=hardware_queue,
    ui_queue=ui_queue,
    ui_type='websocket',  # or 'mqtt'
    port=8000
)

# Start web UI in separate thread
web_thread = threading.Thread(target=launcher)
web_thread.start()
```

## API Endpoints

### WebSocket Endpoints

- `/ws/ui` - UI client connections
- `/ws/recorder/{client_id}` - Recorder service connections

### REST Endpoints

- `GET /` - Serve main UI
- `GET /api/status` - Get all device statuses
- `GET /api/recordings` - List recent recordings

## Communication Protocol

### WebSocket Messages

```javascript
// UI to Server
{
    "type": "command",
    "recorder_id": "recorder_1",
    "action": "start_recording",
    "params": {...}
}

// Server to UI
{
    "type": "status_update",
    "recorder_id": "recorder_1",
    "status": {...}
}
```

### MQTT Topics

- `rslogger/recorder/+/status` - Device status updates
- `rslogger/recorder/+/command` - Commands to devices
- `rslogger/ui/connect` - UI client connections

## Development

### Requirements

- Python 3.8+
- FastAPI
- uvicorn
- websockets
- asyncio-mqtt (for MQTT server)

### Testing

Use `test_recording.html` for basic WebSocket testing:

```bash
python -m http.server 8080
# Open http://localhost:8080/test_recording.html
```

## Integration Notes

The `rslogger_integration.py` module provides:
- `RSLoggerWebBridge`: Bridges async web UI with RSLogger's thread-based architecture
- `DeviceAdapter`: Translates between web UI and RSLogger command formats
- `create_web_ui_launcher`: Factory function for easy integration

## Future Enhancements

- Authentication and user management
- SSL/TLS support
- Database integration for recording history
- Advanced visualization components
- Mobile-responsive improvements