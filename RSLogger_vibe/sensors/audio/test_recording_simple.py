#!/usr/bin/env python3
"""Simple test script to check if audio recording works."""
import asyncio
import sounddevice as sd
import soundfile as sf
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_simple_recording():
    """Test basic audio recording functionality."""
    
    # List devices
    print("Available audio devices:")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"  {i}: {device['name']} ({device['max_input_channels']} ch)")
    
    print(f"\nDefault input device: {sd.default.device[0]}")
    
    # Test recording parameters
    samplerate = 44100
    channels = 1
    duration = 3  # seconds
    
    print(f"\nTesting recording: {duration}s, {samplerate}Hz, {channels} channel(s)")
    
    try:
        # Test creating a stream
        print("Creating test stream...")
        test_stream = sd.InputStream(
            samplerate=samplerate,
            channels=channels,
            dtype='float32'
        )
        test_stream.close()
        print("Stream creation successful")
        
        # Record audio
        print("Starting recording...")
        audio_data = sd.rec(int(duration * samplerate), 
                           samplerate=samplerate, 
                           channels=channels, 
                           dtype='float32')
        
        # Wait for recording to complete
        sd.wait()
        print("Recording completed")
        
        # Save to file
        output_file = Path("test_recording.wav")
        sf.write(str(output_file), audio_data, samplerate)
        print(f"Saved to {output_file}")
        
        # Check audio data
        max_level = np.abs(audio_data).max()
        print(f"Max audio level: {max_level:.4f}")
        
        if max_level > 0.001:
            print("✓ Audio data detected - microphone is working")
        else:
            print("⚠ Very low audio levels - check microphone")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        logger.error("Recording test failed", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_simple_recording())