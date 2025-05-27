# RSLogger VIBE

A unified Video, Audio, and Behavioral Recording system for research applications.

## Overview

RSLogger VIBE combines multiple sensor modules into a single, coordinated recording system:
- **Audio Sensor**: High-quality audio recording with multiple device support
- **Video Sensor**: USB and network camera recording with plugin architecture
- **Web UI**: Browser-based control interface for all sensors

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/RSLogger_vibe.git
cd RSLogger_vibe

# Install with pip
pip install -e .

# Or install with uv
uv pip install -e .
```

## Quick Start

### Launch All Components
```bash
python main.py
```

### Launch Specific Components
```bash
# Audio sensor only
python main.py --components audio

# Video sensor only  
python main.py --components video

# Web UI only
python main.py --components ui

# Multiple components
python main.py --components audio video
```

### Individual Component Usage

#### Audio Sensor
```bash
# Standalone mode
python -m rslogger_vibe.sensors.audio.main

# WebSocket-controlled mode
python -m rslogger_vibe.sensors.audio.main --websocket
```

#### Video Sensor
```bash
# Start video recording server
python -m rslogger_vibe.sensors.video.main

# With specific camera
python -m rslogger_vibe.sensors.video.main --camera-index 1
```

#### Web UI
```bash
# Start web interface
python -m rslogger_vibe.ui.ws_ui_server --port 8080
```

## Architecture

```
RSLogger_vibe/
├── sensors/           # Sensor modules
│   ├── audio/        # Audio recording sensor
│   │   ├── src/      # Source code
│   │   └── tests/    # Unit tests
│   └── video/        # Video recording sensor
│       ├── plugins/  # Camera plugins
│       └── tests/    # Unit tests
├── ui/               # Web user interface
│   ├── static/       # Frontend assets
│   └── *.py          # Server implementations
├── main.py           # Orchestrator script
└── pyproject.toml    # Project configuration
```

## Configuration

### Audio Sensor Configuration
The audio sensor can be configured via:
- Command-line arguments
- Configuration file (`config.json`)
- Environment variables

### Video Sensor Configuration
Video settings are controlled through:
- WebSocket commands
- Plugin-specific parameters
- Camera device selection

## Development

### Running Tests
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=rslogger_vibe
```

### Adding New Sensors
1. Create a new directory under `sensors/`
2. Implement the sensor module with WebSocket interface
3. Update `main.py` to include the new sensor
4. Add dependencies to `pyproject.toml`

## API Documentation

### WebSocket Protocol
All sensors communicate via WebSocket with a common message format:
```json
{
    "action": "start_recording",
    "params": {
        "duration": 60,
        "filename": "recording_001"
    }
}
```

### Common Actions
- `start_recording`: Begin recording
- `stop_recording`: End recording
- `get_status`: Query sensor status
- `configure`: Update sensor settings

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Support

For issues and questions, please use the GitHub issue tracker.