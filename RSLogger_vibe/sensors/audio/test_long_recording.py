#!/usr/bin/env python3
"""Test script for long-duration recording with memory monitoring."""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.recorder import AudioRecorder, RecordingConfig
from src.system_monitor import SystemMonitor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


async def test_long_recording():
    """Test long-duration recording with memory monitoring."""
    
    # Create test config - use lower sample rate for testing
    config = RecordingConfig(
        samplerate=16000,  # Lower for testing
        channels=1,
        dtype='int16',     # Use int16 to save space
        output_dir='test_recordings'
    )
    
    # Create output directory
    Path(config.output_dir).mkdir(exist_ok=True)
    
    # Test duration: 5 seconds for quick test
    # For real RPi deployment, you'd use hours
    test_duration = 5  # 5 seconds
    
    logger.info(f"Starting {test_duration}s test recording")
    logger.info(f"Config: {config.samplerate}Hz, {config.channels}ch, {config.dtype}")
    
    # Check disk space first
    monitor = SystemMonitor()
    space_check = monitor.check_available_space(
        test_duration / 3600, config.samplerate, config.channels, config.dtype
    )
    
    logger.info(f"Disk space check:")
    logger.info(f"  Estimated size: {space_check['estimated_size_gb']*1000:.1f} MB")
    logger.info(f"  Available: {space_check['available_gb']:.1f} GB")
    logger.info(f"  Sufficient: {space_check['sufficient_space']}")
    
    if not space_check['sufficient_space']:
        logger.error("Insufficient disk space!")
        return
        
    # Create recorder and start recording
    recorder = AudioRecorder(config)
    output_path = Path(config.output_dir) / "long_test_recording.wav"
    
    try:
        await recorder.record(output_path, duration=test_duration)
        logger.info("Recording completed successfully!")
        
        # Check file size
        if output_path.exists():
            file_size = output_path.stat().st_size
            logger.info(f"Output file size: {file_size / 1024 / 1024:.1f} MB")
            
            # Verify metadata
            metadata_path = output_path.with_suffix('.json')
            if metadata_path.exists():
                logger.info(f"Metadata file created: {metadata_path}")
            else:
                logger.warning("Metadata file missing!")
        else:
            logger.error("Output file not created!")
            
    except KeyboardInterrupt:
        logger.info("Recording interrupted by user")
    except Exception as e:
        logger.error(f"Recording failed: {e}")


async def test_memory_usage():
    """Test memory usage patterns."""
    monitor = SystemMonitor()
    
    logger.info("Current system stats:")
    stats = monitor.get_system_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            logger.info(f"  {key}: {value:.2f}")
        else:
            logger.info(f"  {key}: {value}")


if __name__ == "__main__":
    print("RSLogger Long Recording Test")
    print("=" * 40)
    print("This tests the streaming recording implementation")
    print("for long-duration recordings on resource-constrained devices.")
    print()
    
    # Test system monitoring first
    print("1. Testing system monitoring...")
    asyncio.run(test_memory_usage())
    print()
    
    # Test recording
    print("2. Testing long recording...")
    print("Press Ctrl+C to stop early if needed")
    print()
    
    asyncio.run(test_long_recording())