# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Guidelines

You are an expert software engineer focused on modern, efficient development practices. Follow these core principles:

**Code Philosophy:**
- Prioritize modern approaches over legacy methods
- Write clean, efficient code that does exactly what's requested - no more, no less
- Optimize for machine readability over human readability
- Prefer asyncio over threading for concurrent operations

**Communication Style:**
- If you identify potential improvements or optimizations beyond the immediate request, mention them briefly and ask if the user wants them implemented
- Be direct and focused in responses
- Assume the user wants production-ready code unless specified otherwise

**Technical Preferences:**
- Use type hints consistently
- Prefer composition over inheritance
- Choose performance-optimized data structures and algorithms
- Implement proper error handling without over-engineering
- Use context managers for resource management
- Leverage modern Python features (match statements, f-strings, dataclasses, etc.)

**Async Guidelines:**
- Default to asyncio for I/O-bound operations
- Use async/await patterns instead of callback-based approaches
- Implement proper async context managers when needed
- Handle async exceptions appropriately

Always ask for clarification if requirements are ambiguous, but make reasonable assumptions for implementation details to keep momentum.

## Project Overview

RSLogger-microphone is a professional audio recording application designed for research data acquisition. It provides both standalone operation and distributed WebSocket-based control for integration into larger logging ecosystems.

**Current Status**: Fully functional with comprehensive test coverage. The module can operate independently or as part of a distributed system controlled via WebSocket.

## Development Commands

```bash
# Install dependencies
pip install -e .

# Run the application
python main.py [options]

# Basic recording (saves to recordings/ directory)
python main.py

# Record with custom settings
python main.py --duration 10 --samplerate 48000 --channels 2

# Device management
python main.py --list-devices  # List all available audio devices
python main.py --info          # Show detailed system audio info
python main.py --device "USB Audio"  # Use specific device by name

# Configuration management
python main.py --save-config   # Save current settings as defaults
python main.py --show-config   # Display current configuration
python main.py --reset-config  # Reset to factory defaults

# Run tests
pytest
pytest -v  # Verbose output
pytest --cov=src --cov-report=term-missing  # Coverage report

# WebSocket Module Operation
python ws_recorder_service.py --id mic1  # Start WebSocket-controlled recorder
python ws_recorder_service.py --id mic1 --server ws://localhost:8080/ws/recorder  # Custom server
python ws_ui_server.py  # Start the web UI server
```

## Architecture Notes

### Standalone Operation

**Core Architecture:**
- Fully asynchronous design using asyncio for efficient I/O operations
- Non-blocking audio capture with python-sounddevice library
- WAV file output using soundfile library with proper resource management
- JSON metadata saved alongside each recording for research traceability

**Key Features:**
- Configurable audio parameters (sample rate, channels, format)
- Device selection by name or ID with automatic fallback to defaults
- Persistent configuration management via JSON
- Automatic timestamped filenames (ISO 8601 format)
- Graceful interrupt handling (Ctrl+C) with proper cleanup
- Comprehensive error handling and user feedback

### WebSocket Distributed Operation

**Architecture:**
- Independent process operation - module crashes don't affect other components
- WebSocket real-time bidirectional communication
- Direct client-server pattern with multiple recorder modules
- Real-time status updates and health monitoring
- Synchronized recording across multiple devices

**WebSocket Components:**
- `ws_recorder_service.py`: WebSocket-enabled audio recorder client
- `ws_ui_server.py`: FastAPI server managing WebSocket connections
- Web UI served from `/static_ui/` directory

**WebSocket Message Types:**
- `register`: Client registration with server
- `command`: Control commands from server to recorder
- `status`: Status updates from recorder to server
- `event`: Recording events (started, completed, error)
- `devices_list`: Available audio devices information

**Key Components:**
- `main.py`: Standalone CLI entry point
- `src/recorder.py`: Core async AudioRecorder class
- `src/config.py`: Basic configuration management
- `ws_recorder_service.py`: WebSocket client for distributed operation
- `ws_ui_server.py`: WebSocket server with web UI

**Data Flow:**
1. Audio callback fills asyncio.Queue with numpy arrays
2. Async coroutine consumes queue and writes to disk
3. Metadata JSON created with recording parameters
4. WebSocket events sent for real-time status updates
5. All operations handled asynchronously for optimal performance

## Dependencies

Core dependencies as defined in `pyproject.toml`:
- Python 3.11+
- sounddevice: Cross-platform audio I/O
- soundfile: Reading and writing audio files
- numpy: Efficient array operations for audio data
- fastapi: Modern web framework for WebSocket server
- uvicorn: ASGI server for running FastAPI
- websockets: WebSocket client/server implementation

Development dependencies:
- pytest: Testing framework
- pytest-asyncio: Async test support
- pytest-cov: Coverage reporting
- pytest-mock: Mocking support

## Testing

The project includes a comprehensive test suite with 85% code coverage:
- `tests/test_recorder.py`: Tests for audio recording functionality
- `tests/test_config.py`: Tests for configuration management
- `tests/test_cli.py`: Tests for CLI argument parsing
- `tests/conftest.py`: Shared pytest fixtures

Run tests with coverage:
```bash
pytest --cov=src --cov-report=term-missing
```

## Usage Examples

### Standalone Recording
```bash
# Basic recording
python main.py

# Record for 30 seconds with custom settings
python main.py --duration 30 --samplerate 48000 --channels 2

# Use specific device
python main.py --device "USB Microphone" --duration 60
```

### Distributed WebSocket Recording
```bash
# Terminal 1 - Start WebSocket UI server
python ws_ui_server.py --port 8080

# Terminal 2 - Start first recorder module
python ws_recorder_service.py --id mic1

# Terminal 3 - Start second recorder module  
python ws_recorder_service.py --id mic2 --device "USB Audio"

# Access the web UI at http://localhost:8080
# Use the web interface to start/stop recordings on all modules
```