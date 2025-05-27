"""WebSocket-based audio recorder service that connects to a central UI server."""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

import websockets
from websockets.client import WebSocketClientProtocol

from .recorder import AudioRecorder, RecordingConfig
from .config import ConfigManager
from .devices import DeviceManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebSocketRecorderClient:
    """WebSocket client that exposes audio recorder controls to external master program."""
    
    def __init__(self, server_url: str, device: Optional[str] = None):
        self.server_url = server_url
        self.device = device
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.recorder: Optional[AudioRecorder] = None
        self.recording_task: Optional[asyncio.Task] = None
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.running = True
        
        # Override device if specified
        if device:
            self.config.device = device
            
    async def connect(self):
        """Connect to the control server."""
        try:
            self.websocket = await websockets.connect(self.server_url)
            logger.info(f"Connected to control server at {self.server_url}")
            
            # Send initial status
            await self.send_status()
            
        except Exception as e:
            logger.error(f"Failed to connect to control server: {e}")
            raise
            
    async def send_message(self, message: Dict[str, Any]):
        """Send a message to the server."""
        if self.websocket:
            try:
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                
    async def send_status(self):
        """Send current status to control server."""
        device_info = await DeviceManager.get_device_info(self.config.device)
        
        status = {
            "type": "status",
            "recording": self.recording_task is not None and not self.recording_task.done(),
            "config": {
                "device": self.config.device,
                "device_name": device_info.name,
                "samplerate": self.config.samplerate,
                "channels": self.config.channels,
                "dtype": self.config.dtype,
                "output_dir": self.config.output_dir
            },
            "capabilities": await self.get_capabilities()
        }
        
        await self.send_message(status)
        
    async def get_capabilities(self):
        """Get recorder capabilities including available devices and supported settings."""
        devices = await DeviceManager.list_input_devices()
        
        return {
            "devices": [
                {
                    "id": dev.id,
                    "name": dev.name,
                    "channels": dev.channels,
                    "default_samplerate": dev.samplerate,
                    "is_current": dev.id == self.config.device or dev.name == self.config.device
                }
                for dev in devices
            ],
            "supported_samplerates": [8000, 16000, 22050, 44100, 48000, 96000, 192000],
            "supported_channels": [1, 2],
            "supported_dtypes": ["int16", "int32", "float32"],
            "max_recording_duration": 3600  # 1 hour max
        }
        
    async def handle_command(self, command: str, payload: Dict[str, Any]):
        """Handle commands from the control server."""
        logger.info(f"Received command: {command}")
        
        if command == "start_recording":
            await self.start_recording(payload.get("duration"), payload.get("filename"))
            
        elif command == "stop_recording":
            await self.stop_recording()
            
        elif command == "get_status":
            await self.send_status()
            
        elif command == "update_config":
            await self.update_config(payload)
            
        elif command == "get_capabilities":
            await self.send_message({
                "type": "capabilities",
                "capabilities": await self.get_capabilities()
            })
            
        elif command == "list_devices":
            devices = await DeviceManager.list_input_devices()
            await self.send_message({
                "type": "devices_list",
                "devices": [
                    {
                        "id": dev.id,
                        "name": dev.name,
                        "channels": dev.channels,
                        "samplerate": dev.samplerate
                    }
                    for dev in devices
                ]
            })
            
        elif command == "shutdown":
            logger.info("Received shutdown command")
            self.running = False
            
    async def start_recording(self, duration: Optional[float] = None, filename: Optional[str] = None):
        """Start audio recording."""
        if self.recording_task and not self.recording_task.done():
            await self.send_message({
                "type": "error",
                "error": "Already recording"
            })
            return
            
        try:
            # Create recorder
            self.recorder = AudioRecorder(self.config)
            
            # Use provided filename or generate one
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                device_info = await DeviceManager.get_device_info(self.config.device)
                device_name = device_info.name.replace(" ", "_").lower()
                filename = f"recording_{timestamp}_{device_name}.wav"
            
            output_path = Path(self.config.output_dir) / filename
            output_path.parent.mkdir(exist_ok=True)
            
            # Send recording started event
            await self.send_message({
                "type": "event",
                "event": "recording_started",
                "filename": filename,
                "timestamp": datetime.now().isoformat()
            })
            
            # Start recording task
            self.recording_task = asyncio.create_task(
                self._record(output_path, duration)
            )
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            await self.send_message({
                "type": "event",
                "event": "recording_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            
    async def _record(self, output_path: Path, duration: Optional[float]):
        """Perform the actual recording."""
        try:
            await self.recorder.record(output_path, duration)
            
            # Send recording completed event
            await self.send_message({
                "type": "event",
                "event": "recording_completed",
                "filename": output_path.name,
                "timestamp": datetime.now().isoformat()
            })
            
        except asyncio.CancelledError:
            logger.info("Recording cancelled")
            # Send recording stopped event
            await self.send_message({
                "type": "event",
                "event": "recording_stopped",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Recording error: {e}")
            await self.send_message({
                "type": "event",
                "event": "recording_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
        finally:
            self.recording_task = None
            await self.send_status()
            
    async def stop_recording(self):
        """Stop current recording."""
        if self.recording_task and not self.recording_task.done():
            if self.recorder:
                self.recorder.stop()
            self.recording_task.cancel()
            try:
                await self.recording_task
            except asyncio.CancelledError:
                pass
        else:
            await self.send_message({
                "type": "error",
                "error": "Not recording"
            })
            
    async def update_config(self, config_update: Dict[str, Any]):
        """Update configuration."""
        try:
            for key, value in config_update.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                    
            self.config_manager.save(self.config)
            await self.send_status()
            
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            await self.send_message({
                "type": "error",
                "error": f"Config update failed: {str(e)}"
            })
            
    async def run(self):
        """Main run loop."""
        while self.running:
            try:
                await self.connect()
                
                # Listen for messages
                async for message in self.websocket:
                    try:
                        data = json.loads(message)
                        
                        if data.get("type") == "command":
                            command = data.get("command")
                            payload = data.get("payload", {})
                            await self.handle_command(command, payload)
                            
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON message: {message}")
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection closed, reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Connection error: {e}")
                await asyncio.sleep(5)
                
            if not self.running:
                break
                
    async def shutdown(self):
        """Clean shutdown."""
        self.running = False
        
        # Stop any active recording
        if self.recording_task and not self.recording_task.done():
            await self.stop_recording()
            
        # Close websocket
        if self.websocket:
            await self.websocket.close()


