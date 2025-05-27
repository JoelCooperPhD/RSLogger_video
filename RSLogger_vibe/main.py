#!/usr/bin/env python3
"""
RSLogger VIBE - Unified Video, Audio, and Behavioral Recording System

This script orchestrates the launch of multiple RSLogger components:
- Audio recording sensor
- Video recording sensor  
- Web UI interface
"""

import asyncio
import argparse
import logging
import sys
import subprocess
import signal
from pathlib import Path
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rslogger-vibe')


class RSLoggerOrchestrator:
    """Manages launching and coordinating RSLogger components."""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.running = False
        
    def start_audio_sensor(self, args: List[str] = None) -> subprocess.Popen:
        """Start the audio recording sensor."""
        cmd = [sys.executable, "-m", "rslogger_vibe.sensors.audio.main"]
        if args:
            cmd.extend(args)
        
        logger.info("Starting audio sensor...")
        process = subprocess.Popen(cmd)
        self.processes.append(process)
        return process
        
    def start_video_sensor(self, args: List[str] = None) -> subprocess.Popen:
        """Start the video recording sensor."""
        cmd = [sys.executable, "-m", "rslogger_vibe.sensors.video.main"]
        if args:
            cmd.extend(args)
            
        logger.info("Starting video sensor...")
        process = subprocess.Popen(cmd)
        self.processes.append(process)
        return process
        
    def start_web_ui(self, host: str = "0.0.0.0", port: int = 8080) -> subprocess.Popen:
        """Start the web UI server."""
        cmd = [
            sys.executable, "-m", "rslogger_vibe.ui.ws_ui_server",
            "--host", host,
            "--port", str(port)
        ]
        
        logger.info(f"Starting web UI on {host}:{port}...")
        process = subprocess.Popen(cmd)
        self.processes.append(process)
        return process
        
    def stop_all(self):
        """Stop all running processes."""
        logger.info("Stopping all components...")
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    
        self.processes.clear()
        
    async def monitor_processes(self):
        """Monitor running processes and restart if needed."""
        while self.running:
            for i, process in enumerate(self.processes):
                if process.poll() is not None:
                    logger.warning(f"Process {i} exited with code {process.returncode}")
                    
            await asyncio.sleep(1)
            
    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal...")
        self.running = False
        self.stop_all()
        sys.exit(0)


async def main():
    parser = argparse.ArgumentParser(
        description="RSLogger VIBE - Unified recording system orchestrator"
    )
    parser.add_argument(
        "--components",
        nargs="+",
        choices=["audio", "video", "ui", "all"],
        default=["all"],
        help="Components to start"
    )
    parser.add_argument(
        "--ui-host",
        default="0.0.0.0",
        help="Web UI host address"
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=8080,
        help="Web UI port"
    )
    parser.add_argument(
        "--audio-args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to audio sensor"
    )
    parser.add_argument(
        "--video-args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to video sensor"
    )
    
    args = parser.parse_args()
    
    orchestrator = RSLoggerOrchestrator()
    orchestrator.running = True
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, orchestrator.signal_handler)
    signal.signal(signal.SIGTERM, orchestrator.signal_handler)
    
    components = args.components
    if "all" in components:
        components = ["audio", "video", "ui"]
    
    try:
        # Start requested components
        if "audio" in components:
            orchestrator.start_audio_sensor(args.audio_args)
            
        if "video" in components:
            orchestrator.start_video_sensor(args.video_args)
            
        if "ui" in components:
            orchestrator.start_web_ui(args.ui_host, args.ui_port)
            
        logger.info("All components started. Press Ctrl+C to stop.")
        
        # Monitor processes
        await orchestrator.monitor_processes()
        
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        orchestrator.stop_all()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())