#!/usr/bin/env python3
"""WebSocket-based UI server for controlling audio recorders."""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import argparse
import sys
import signal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="RSLogger WebSocket Control UI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecorderConnection:
    """Represents a connected recorder client."""
    def __init__(self, client_id: str, websocket: WebSocket):
        self.client_id = client_id
        self.websocket = websocket
        self.status = {}
        

class WebSocketUIManager:
    """Manages WebSocket connections for both UI clients and recorder services."""
    
    def __init__(self):
        self.ui_connections: List[WebSocket] = []
        self.recorder_connections: Dict[str, RecorderConnection] = {}
        self.recordings: List[Dict[str, Any]] = []
        
    async def connect_ui(self, websocket: WebSocket):
        """Handle new UI client connection."""
        await websocket.accept()
        self.ui_connections.append(websocket)
        
        # Send initial state
        await websocket.send_json({
            "type": "initial_state",
            "recorders": self.get_recorders_status(),
            "recordings": await self.get_recordings()
        })
        
    async def connect_recorder(self, websocket: WebSocket):
        """Handle new recorder service connection."""
        await websocket.accept()
        # Wait for registration message to get client_id
        
    def disconnect_ui(self, websocket: WebSocket):
        """Handle UI client disconnection."""
        if websocket in self.ui_connections:
            self.ui_connections.remove(websocket)
            
    def disconnect_recorder(self, client_id: str):
        """Handle recorder service disconnection."""
        if client_id in self.recorder_connections:
            del self.recorder_connections[client_id]
            # Notify UI clients
            asyncio.create_task(self.broadcast_to_ui({
                "type": "recorder_disconnected",
                "client_id": client_id
            }))
            
    async def handle_recorder_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Handle messages from recorder services."""
        msg_type = message.get("type")
        client_id = message.get("client_id")
        
        if msg_type == "register":
            # Register new recorder
            self.recorder_connections[client_id] = RecorderConnection(client_id, websocket)
            logger.info(f"Recorder {client_id} registered")
            
            # Notify UI clients
            await self.broadcast_to_ui({
                "type": "recorder_connected",
                "client_id": client_id
            })
            
        elif msg_type == "status":
            # Update recorder status
            if client_id in self.recorder_connections:
                self.recorder_connections[client_id].status = message
                
            # Forward to UI clients
            await self.broadcast_to_ui({
                "type": "recorder_status",
                "client_id": client_id,
                "status": message
            })
            
        elif msg_type == "event":
            # Handle recorder events
            event = message.get("event")
            
            if event == "recording_completed":
                # Update recordings list
                await self.update_recordings()
                
            # Forward event to UI clients
            await self.broadcast_to_ui({
                "type": f"recorder_{event}",
                "client_id": client_id,
                "data": message
            })
            
        elif msg_type == "error":
            # Forward error to UI clients
            await self.broadcast_to_ui({
                "type": "recorder_error",
                "client_id": client_id,
                "error": message.get("error")
            })
            
        elif msg_type == "devices_list":
            # Forward devices list to UI clients
            await self.broadcast_to_ui({
                "type": "devices_list",
                "client_id": client_id,
                "devices": message.get("devices", [])
            })
            
    async def handle_ui_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Handle messages from UI clients."""
        msg_type = message.get("type")
        
        if msg_type == "command":
            client_id = message.get("client_id")
            command = message.get("command")
            payload = message.get("payload", {})
            
            if client_id == "all":
                # Broadcast to all recorders
                await self.broadcast_command_to_recorders(command, payload)
            elif client_id in self.recorder_connections:
                # Send to specific recorder
                await self.send_command_to_recorder(client_id, command, payload)
            else:
                await websocket.send_json({
                    "type": "error",
                    "error": f"Recorder {client_id} not connected"
                })
                
        elif msg_type == "refresh_recorders":
            # Request status from all recorders
            await self.broadcast_command_to_recorders("get_status")
            
        elif msg_type == "get_recordings":
            recordings = await self.get_recordings()
            await websocket.send_json({
                "type": "recordings_list",
                "recordings": recordings
            })
            
    async def send_command_to_recorder(self, client_id: str, command: str, payload: Dict[str, Any] = None):
        """Send command to specific recorder."""
        if client_id in self.recorder_connections:
            recorder = self.recorder_connections[client_id]
            try:
                await recorder.websocket.send_json({
                    "type": "command",
                    "command": command,
                    "payload": payload or {}
                })
                logger.info(f"Sent command '{command}' to {client_id}")
            except Exception as e:
                logger.error(f"Error sending command to {client_id}: {e}")
                self.disconnect_recorder(client_id)
                
    async def broadcast_command_to_recorders(self, command: str, payload: Dict[str, Any] = None):
        """Broadcast command to all recorders."""
        disconnected = []
        for client_id, recorder in self.recorder_connections.items():
            try:
                await recorder.websocket.send_json({
                    "type": "command",
                    "command": command,
                    "payload": payload or {}
                })
            except Exception:
                disconnected.append(client_id)
                
        for client_id in disconnected:
            self.disconnect_recorder(client_id)
            
    async def broadcast_to_ui(self, message: Dict[str, Any]):
        """Broadcast message to all UI clients."""
        disconnected = []
        for connection in self.ui_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
                
        for conn in disconnected:
            self.disconnect_ui(conn)
            
    def get_recorders_status(self) -> Dict[str, Any]:
        """Get status of all connected recorders."""
        return {
            client_id: recorder.status
            for client_id, recorder in self.recorder_connections.items()
        }
        
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
        """Update recordings list and notify UI clients."""
        self.recordings = await self.get_recordings()
        await self.broadcast_to_ui({
            "type": "recordings_updated",
            "recordings": self.recordings
        })


# Create global manager
manager = WebSocketUIManager()

@app.websocket("/ws")
async def websocket_ui_endpoint(websocket: WebSocket):
    """WebSocket endpoint for UI clients."""
    await manager.connect_ui(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_ui_message(websocket, data)
            
    except WebSocketDisconnect:
        manager.disconnect_ui(websocket)
    except Exception as e:
        logger.error(f"UI WebSocket error: {e}")
        manager.disconnect_ui(websocket)

@app.websocket("/ws/recorder")
async def websocket_recorder_endpoint(websocket: WebSocket):
    """WebSocket endpoint for recorder services."""
    await manager.connect_recorder(websocket)
    client_id = None
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Extract client_id from registration or any message
            if not client_id and data.get("client_id"):
                client_id = data.get("client_id")
                
            await manager.handle_recorder_message(websocket, data)
            
    except WebSocketDisconnect:
        if client_id:
            manager.disconnect_recorder(client_id)
    except Exception as e:
        logger.error(f"Recorder WebSocket error: {e}")
        if client_id:
            manager.disconnect_recorder(client_id)

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


# Global server instance for shutdown
server_instance = None

async def shutdown_server():
    """Gracefully shutdown the server."""
    global server_instance
    if server_instance:
        logger.info("Initiating server shutdown...")
        server_instance.should_exit = True

async def main():
    global server_instance
    
    parser = argparse.ArgumentParser(description="WebSocket UI Server")
    parser.add_argument("--port", type=int, default=8080, help="Web server port")
    
    args = parser.parse_args()
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(shutdown_server())
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run web server
    config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=args.port, 
        log_level="info",
        loop="asyncio"
    )
    server_instance = uvicorn.Server(config)
    
    try:
        await server_instance.serve()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Server shutdown complete")
    finally:
        # Cleanup
        server_instance = None


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nServer stopped.")
        sys.exit(0)