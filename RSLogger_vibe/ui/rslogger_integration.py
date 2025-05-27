"""Integration module for connecting Web UI with RSLogger's architecture.

This module bridges the gap between the modern web-based UI servers and
RSLogger's existing thread-based hardware interface architecture.
"""

import asyncio
import threading
import queue
import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class RSLoggerWebBridge:
    """Bridge between RSLogger's thread-based architecture and async web UI."""
    
    def __init__(self, hardware_queue: queue.Queue, ui_queue: queue.Queue):
        """Initialize the bridge with RSLogger's communication queues.
        
        Args:
            hardware_queue: Queue for sending commands to hardware interfaces
            ui_queue: Queue for receiving updates from hardware interfaces
        """
        self.hardware_queue = hardware_queue
        self.ui_queue = ui_queue
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.update_callbacks: Dict[str, Callable] = {}
        self.running = False
        self._thread = None
        
    def register_update_callback(self, event_type: str, callback: Callable):
        """Register a callback for specific update types.
        
        Args:
            event_type: Type of event (e.g., 'status', 'data', 'error')
            callback: Async function to call with update data
        """
        self.update_callbacks[event_type] = callback
        
    def send_command(self, device_id: str, command: Dict[str, Any]):
        """Send a command to hardware interface.
        
        Args:
            device_id: ID of the target device
            command: Command dictionary
        """
        message = {
            'device_id': device_id,
            'command': command,
            'timestamp': asyncio.get_event_loop().time()
        }
        self.hardware_queue.put(message)
        logger.debug(f"Sent command to {device_id}: {command}")
        
    async def _process_ui_updates(self):
        """Process updates from hardware interfaces."""
        while self.running:
            try:
                # Check for updates with timeout
                update = await asyncio.get_event_loop().run_in_executor(
                    None, self.ui_queue.get, True, 0.1
                )
                
                # Determine update type and call appropriate callback
                update_type = update.get('type', 'unknown')
                if update_type in self.update_callbacks:
                    await self.update_callbacks[update_type](update)
                else:
                    logger.warning(f"No callback registered for update type: {update_type}")
                    
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error processing UI update: {e}")
                
    def start(self):
        """Start the bridge in a separate thread."""
        if self.running:
            logger.warning("Bridge already running")
            return
            
        self.running = True
        self._thread = threading.Thread(target=self._run_async_loop)
        self._thread.daemon = True
        self._thread.start()
        logger.info("RSLogger Web Bridge started")
        
    def _run_async_loop(self):
        """Run the async event loop in a thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._process_ui_updates())
        except Exception as e:
            logger.error(f"Bridge async loop error: {e}")
        finally:
            self.loop.close()
            
    def stop(self):
        """Stop the bridge."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("RSLogger Web Bridge stopped")


class DeviceAdapter:
    """Adapter for translating between web UI commands and RSLogger device commands."""
    
    # Map web UI commands to RSLogger device commands
    COMMAND_MAP = {
        'start_recording': {'action': 'start_experiment'},
        'stop_recording': {'action': 'stop_experiment'},
        'pause_recording': {'action': 'pause_experiment'},
        'resume_recording': {'action': 'resume_experiment'},
        'get_status': {'action': 'get_status'},
        'set_config': {'action': 'update_config'},
    }
    
    @classmethod
    def translate_web_command(cls, web_command: Dict[str, Any]) -> Dict[str, Any]:
        """Translate a web UI command to RSLogger format.
        
        Args:
            web_command: Command from web UI
            
        Returns:
            Translated command for RSLogger hardware interface
        """
        cmd_type = web_command.get('type')
        if cmd_type not in cls.COMMAND_MAP:
            raise ValueError(f"Unknown command type: {cmd_type}")
            
        rslogger_cmd = cls.COMMAND_MAP[cmd_type].copy()
        
        # Add any additional parameters
        if 'params' in web_command:
            rslogger_cmd['params'] = web_command['params']
            
        return rslogger_cmd
        
    @classmethod
    def translate_device_update(cls, device_update: Dict[str, Any]) -> Dict[str, Any]:
        """Translate a device update to web UI format.
        
        Args:
            device_update: Update from RSLogger device
            
        Returns:
            Translated update for web UI
        """
        # Extract common fields
        web_update = {
            'device_id': device_update.get('device_id'),
            'timestamp': device_update.get('timestamp'),
            'type': device_update.get('type', 'status'),
        }
        
        # Translate status updates
        if web_update['type'] == 'status':
            web_update['status'] = {
                'recording': device_update.get('experiment_running', False),
                'connected': device_update.get('connected', False),
                'battery': device_update.get('battery_level'),
                'storage': device_update.get('storage_available'),
            }
            
        # Translate data updates
        elif web_update['type'] == 'data':
            web_update['data'] = device_update.get('data', {})
            
        return web_update


def create_web_ui_launcher(hardware_queue: queue.Queue, ui_queue: queue.Queue, 
                          ui_type: str = 'websocket', port: int = 8000):
    """Create a launcher function for integrating web UI with RSLogger.
    
    Args:
        hardware_queue: Queue for hardware commands
        ui_queue: Queue for UI updates
        ui_type: Type of UI server ('websocket' or 'mqtt')
        port: Port to run the web UI on
        
    Returns:
        Function to launch the web UI server
    """
    def launch_web_ui():
        # Create bridge
        bridge = RSLoggerWebBridge(hardware_queue, ui_queue)
        
        # Import appropriate server module
        if ui_type == 'websocket':
            from . import ws_ui_server as ui_server
        else:
            from . import mqtt_ui_server as ui_server
            
        # Inject bridge into server (this would require modifying the server files)
        # For now, we'll just start the bridge
        bridge.start()
        
        # Run the UI server
        import uvicorn
        uvicorn.run(ui_server.app, host="0.0.0.0", port=port)
        
    return launch_web_ui