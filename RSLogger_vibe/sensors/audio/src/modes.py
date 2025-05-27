"""Operation modes for RSLogger Audio."""

import asyncio
import logging
from typing import Optional
from pathlib import Path
from datetime import datetime
import signal
from types import FrameType

logger = logging.getLogger(__name__)


async def run_standalone_recording(config, args):
    """Run standalone audio recording mode."""
    from .recorder import AudioRecorder
    from .devices import DeviceManager
    
    recorder = AudioRecorder(config)
    
    # Handle device listing
    if args.list_devices:
        devices = await DeviceManager.list_input_devices()
        print("Available input devices:")
        for dev in devices:
            print(f"  {dev.id}: {dev.name} ({dev.channels} ch, {int(dev.samplerate)} Hz)")
        return
    
    # Handle device info request
    if args.info:
        info = await DeviceManager.get_device_info(config.device)
        device_label = f"Device {info.id}" if info.id is not None else "Default Device"
        print(f"{device_label}:")
        print(f"  Name: {info.name}")
        print(f"  Max channels: {info.channels}")
        print(f"  Default sample rate: {info.samplerate} Hz")
        return
    
    # Generate filename if not provided
    filename = args.filename
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Get device info for filename
        device_info = await DeviceManager.get_device_info(config.device)
        device_id = f"_device{device_info.id}" if device_info.id is not None else ""
        filename = f"recording_{timestamp}{device_id}.wav"
    
    # Ensure .wav extension
    if not filename.endswith('.wav'):
        filename += '.wav'
    
    # Create output path
    output_path = Path(config.output_dir) / filename
    output_path.parent.mkdir(exist_ok=True)
    
    # Start recording
    await handle_recording(recorder, output_path, args.duration)


async def handle_recording(recorder, output_path: Path, duration: Optional[float]) -> None:
    """Handle the recording process with proper signal handling."""
    # Create task for recording
    recording_task = asyncio.create_task(
        recorder.record(output_path, duration)
    )
    
    # Setup signal handler for graceful shutdown
    def signal_handler(_sig: int, _frame: Optional[FrameType]) -> None:
        recorder.stop()
        recording_task.cancel()
        
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        await recording_task
    except asyncio.CancelledError:
        logger.info("Recording stopped by user")




async def run_controlled_mode(server_url: str, device: Optional[str] = None) -> None:
    """Run in controlled mode - expose recorder controls via WebSocket."""
    from .websocket_client import WebSocketRecorderClient
    
    # Create client that exposes our recorder controls
    client = WebSocketRecorderClient(server_url, device)
    
    # Create shutdown event
    shutdown_event = asyncio.Event()
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, initiating shutdown...")
        shutdown_event.set()
        # Schedule shutdown
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(client.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run client with shutdown monitoring
    run_task = asyncio.create_task(client.run())
    shutdown_task = asyncio.create_task(shutdown_event.wait())
    
    try:
        # Wait for either normal completion or shutdown signal
        done, pending = await asyncio.wait(
            {run_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await client.shutdown()
        # Give a moment for cleanup
        await asyncio.sleep(0.5)