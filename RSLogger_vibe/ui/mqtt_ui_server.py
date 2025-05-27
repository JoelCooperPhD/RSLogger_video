#!/usr/bin/env python3
"""MQTT-based Web UI server for controlling audio recorders."""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import argparse

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from asyncio_mqtt import Client as MQTTClient
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="RSLogger MQTT Control UI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MQTTUIManager:
    """Manages MQTT communication and WebSocket connections."""
    
    def __init__(self, broker: str = "localhost", port: int = 1883):
        self.broker = broker
        self.port = port
        self.mqtt_client: Optional[MQTTClient] = None
        self.active_connections: List[WebSocket] = []
        self.recorder_status: Dict[str, Any] = {}
        self.recordings: List[Dict[str, Any]] = []
        self.mqtt_task: Optional[asyncio.Task] = None
        
    async def start_mqtt(self):
        """Start MQTT client and subscribe to topics."""
        try:
            self.mqtt_client = MQTTClient(self.broker, self.port)
            await self.mqtt_client.connect()
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            
            # Subscribe to all recorder topics
            await self.mqtt_client.subscribe("rslogger/audio/+/status")
            await self.mqtt_client.subscribe("rslogger/audio/+/response")
            await self.mqtt_client.subscribe("rslogger/audio/+/data")
            
            # Start listening for messages
            self.mqtt_task = asyncio.create_task(self._mqtt_listener())
            
            # Request status from all recorders
            await self.broadcast_command("get_status")
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            
    async def _mqtt_listener(self):
        """Listen for MQTT messages."""
        async with self.mqtt_client.messages() as messages:
            async for message in messages:
                try:
                    topic = str(message.topic)
                    payload = json.loads(message.payload.decode())
                    
                    # Extract client_id from topic
                    parts = topic.split('/')
                    if len(parts) >= 4:
                        client_id = parts[2]
                        message_type = parts[3]
                        
                        if message_type == "status":
                            await self.handle_status(client_id, payload)
                        elif message_type == "response":
                            await self.handle_response(client_id, payload)
                        elif message_type == "data":
                            await self.handle_data(client_id, payload)
                            
                except Exception as e:
                    logger.error(f"Error processing MQTT message: {e}", exc_info=True)
                    
    async def handle_status(self, client_id: str, status: Dict[str, Any]):
        """Handle recorder status updates."""
        self.recorder_status[client_id] = status
        await self.broadcast_to_websockets({
            "type": "recorder_status",
            "client_id": client_id,
            "status": status
        })
        
    async def handle_response(self, client_id: str, response: Dict[str, Any]):
        """Handle command responses."""
        await self.broadcast_to_websockets({
            "type": "command_response",
            "client_id": client_id,
            "response": response
        })
        
    async def handle_data(self, client_id: str, data: Dict[str, Any]):
        """Handle data events from recorders."""
        event = data.get("event")
        
        if event == "recording_started":
            await self.broadcast_to_websockets({
                "type": "recording_started",
                "client_id": client_id,
                "timestamp": data.get("timestamp")
            })
            
        elif event == "recording_completed":
            # Update recordings list
            await self.update_recordings()
            await self.broadcast_to_websockets({
                "type": "recording_completed",
                "client_id": client_id,
                "filename": data.get("filename"),
                "timestamp": data.get("timestamp")
            })
            
        elif event == "recording_error":
            await self.broadcast_to_websockets({
                "type": "recording_error",
                "client_id": client_id,
                "error": data.get("error"),
                "timestamp": data.get("timestamp")
            })
            
    async def send_command(self, client_id: str, command: str, payload: Dict[str, Any] = None):
        """Send command to specific recorder."""
        if not self.mqtt_client:
            return
            
        command_data = {"command": command}
        if payload:
            command_data.update(payload)
            
        topic = f"rslogger/audio/{client_id}/command"
        await self.mqtt_client.publish(topic, json.dumps(command_data).encode())
        logger.info(f"Sent command '{command}' to {client_id}")
        
    async def broadcast_command(self, command: str, payload: Dict[str, Any] = None):
        """Broadcast command to all recorders."""
        for client_id in self.recorder_status.keys():
            await self.send_command(client_id, command, payload)
            
    async def connect_websocket(self, websocket: WebSocket):
        """Handle new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Send initial state
        await websocket.send_json({
            "type": "initial_state",
            "recorders": self.recorder_status,
            "recordings": await self.get_recordings()
        })
        
    def disconnect_websocket(self, websocket: WebSocket):
        """Handle WebSocket disconnection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
    async def broadcast_to_websockets(self, message: Dict[str, Any]):
        """Broadcast message to all WebSocket connections."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
                
        for conn in disconnected:
            self.disconnect_websocket(conn)
            
    async def get_recordings(self) -> List[Dict[str, Any]]:
        """Get list of all recordings."""
        recordings = []
        recordings_dir = Path("recordings")
        
        if recordings_dir.exists():
            for json_file in recordings_dir.glob("*.json"):
                try:
                    with open(json_file, 'r') as f:
                        metadata = json.load(f)
                    wav_file = json_file.with_suffix('.wav')
                    if wav_file.exists():
                        recordings.append({
                            "filename": wav_file.name,
                            "metadata": metadata,
                            "size": wav_file.stat().st_size,
                            "created": datetime.fromtimestamp(wav_file.stat().st_ctime).isoformat()
                        })
                except Exception as e:
                    logger.error(f"Error reading recording: {e}")
                    
        return sorted(recordings, key=lambda x: x['created'], reverse=True)
        
    async def update_recordings(self):
        """Update recordings list and notify clients."""
        self.recordings = await self.get_recordings()
        await self.broadcast_to_websockets({
            "type": "recordings_updated",
            "recordings": self.recordings
        })


# Create global manager
manager = MQTTUIManager()

@app.on_event("startup")
async def startup_event():
    """Start MQTT client on server startup."""
    await manager.start_mqtt()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect_websocket(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "command":
                client_id = data.get("client_id")
                command = data.get("command")
                payload = data.get("payload", {})
                
                if client_id == "all":
                    await manager.broadcast_command(command, payload)
                else:
                    await manager.send_command(client_id, command, payload)
                    
            elif data["type"] == "refresh_recorders":
                await manager.broadcast_command("get_status")
                
            elif data["type"] == "get_recordings":
                recordings = await manager.get_recordings()
                await websocket.send_json({
                    "type": "recordings_list",
                    "recordings": recordings
                })
                
    except WebSocketDisconnect:
        manager.disconnect_websocket(websocket)

@app.get("/api/recordings/{filename}")
async def download_recording(filename: str):
    """Download a recording file."""
    file_path = Path("recordings") / filename
    if not file_path.exists() or not file_path.is_file():
        return JSONResponse(status_code=404, content={"error": "Recording not found"})
    return FileResponse(file_path, media_type="audio/wav", filename=filename)

# Serve static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def read_index():
    """Serve the main index.html page."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    else:
        return JSONResponse(status_code=404, content={"error": "Index file not found"})


import signal
import sys

# Global server instance for signal handling
server_instance = None
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_event.set()
    if server_instance:
        server_instance.should_exit = True
    sys.exit(0)

async def main():
    global server_instance
    
    parser = argparse.ArgumentParser(description="MQTT UI Server")
    parser.add_argument("--broker", default="localhost", help="MQTT broker address")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--web-port", type=int, default=8080, help="Web server port")
    
    args = parser.parse_args()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Update manager with broker settings
    manager.broker = args.broker
    manager.port = args.mqtt_port
    
    # Run web server
    config = uvicorn.Config(app, host="0.0.0.0", port=args.web_port, log_level="info")
    server_instance = uvicorn.Server(config)
    
    try:
        await server_instance.serve()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        if manager.mqtt_client:
            await manager.mqtt_client.disconnect()
        logger.info("Cleanup complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
        sys.exit(0)