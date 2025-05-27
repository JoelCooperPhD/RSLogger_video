import asyncio
import sounddevice as sd
import soundfile as sf
import numpy as np
import logging
import threading
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
from dataclasses import dataclass, asdict
import json
from datetime import datetime
import time

from .exceptions import RecordingError, DeviceNotFoundError, ConfigurationError
from .enums import AudioFormat, RecordingState
from .devices import DeviceManager, AudioDevice
from .system_monitor import SystemMonitor


logger = logging.getLogger(__name__)


@dataclass
class RecordingConfig:
    samplerate: int = 44100
    channels: int = 1
    dtype: str = AudioFormat.FLOAT32.value
    output_dir: str = 'recordings'
    device: Optional[Union[int, str]] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.samplerate <= 0:
            raise ConfigurationError("Sample rate must be positive")
        if self.channels not in (1, 2):
            raise ConfigurationError("Channels must be 1 (mono) or 2 (stereo)")
        if not AudioFormat.is_valid(self.dtype):
            raise ConfigurationError(f"Unsupported dtype: {self.dtype}")
    
    
class AudioRecorder:
    def __init__(self, config: RecordingConfig = RecordingConfig()):
        self.config = config
        self._state = RecordingState.IDLE
        self._recording = False  # Keep for backward compatibility
        self._audio_queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=500)  # Limit queue size
        self._device_info: Optional[Dict[str, Any]] = None
        self._last_audio_data: Optional[np.ndarray] = None  # For level monitoring
        self._file_writer: Optional[sf.SoundFile] = None
        self._write_lock = threading.Lock()
        self._total_frames_written = 0
        self._start_time: Optional[float] = None
        self._system_monitor = SystemMonitor()
        
    def _audio_callback(self, indata: np.ndarray, frames: int, 
                       time_info: Any, status: sd.CallbackFlags) -> None:
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        try:
            self._audio_queue.put_nowait(indata.copy())
            self._last_audio_data = indata.copy()  # Store for level monitoring
        except asyncio.QueueFull:
            logger.warning("Audio queue full, dropping frames")
            
    async def record(self, output_path: Path, duration: Optional[float] = None) -> None:
        logger.info(f"Recording to {output_path}")
        if duration:
            logger.info(f"Recording for {duration} seconds")
        else:
            logger.info("Press Ctrl+C to stop recording")
            
        self._state = RecordingState.RECORDING
        self._recording = True  # Keep for backward compatibility
        self._total_frames_written = 0
        self._start_time = time.time()
        
        # Start system monitoring
        await self._system_monitor.start_monitoring()
        
        # Check available disk space if duration is specified
        if duration:
            space_check = self._system_monitor.check_available_space(
                duration / 3600, self.config.samplerate, self.config.channels, self.config.dtype
            )
            if not space_check['sufficient_space']:
                logger.warning(f"Insufficient disk space! Need {space_check['estimated_size_gb']:.1f}GB, "
                             f"have {space_check['available_gb']:.1f}GB")
                logger.warning(f"Max recording duration: {space_check['max_duration_hours']:.1f} hours")
        
        # Get device info before recording
        device_info = await DeviceManager.get_device_info(self.config.device)
        self._device_info = asdict(device_info)
        
        # Open file for streaming writes
        loop = asyncio.get_event_loop()
        self._file_writer = await loop.run_in_executor(
            None,
            lambda: sf.SoundFile(
                str(output_path),
                'w',
                samplerate=self.config.samplerate,
                channels=self.config.channels,
                format='WAV',
                subtype='FLOAT' if self.config.dtype == 'float32' else 'PCM_16'
            )
        )
        
        stream = sd.InputStream(
            samplerate=self.config.samplerate,
            channels=self.config.channels,
            dtype=self.config.dtype,
            device=self.config.device,
            callback=self._audio_callback
        )
        
        try:
            with stream:
                start_time = asyncio.get_event_loop().time()
                
                # Start background writer task
                writer_task = asyncio.create_task(self._stream_writer())
                
                while self._state == RecordingState.RECORDING:
                    if duration and (asyncio.get_event_loop().time() - start_time) >= duration:
                        break
                    
                    # Just sleep, let the writer task handle the queue
                    await asyncio.sleep(0.1)
                
                # Stop writer task
                writer_task.cancel()
                try:
                    await writer_task
                except asyncio.CancelledError:
                    pass
                        
        except asyncio.CancelledError:
            logger.info("Recording cancelled")
            raise
        finally:
            self._state = RecordingState.IDLE
            self._recording = False  # Keep for backward compatibility
            await self._system_monitor.stop_monitoring()
            await self._close_file_and_save_metadata(output_path)
            
    async def _stream_writer(self) -> None:
        """Background task that writes audio chunks to disk as they arrive."""
        chunks_to_write = []
        last_write_time = time.time()
        
        while self._state == RecordingState.RECORDING:
            try:
                # Collect multiple chunks before writing to reduce I/O overhead
                chunk = await asyncio.wait_for(
                    self._audio_queue.get(),
                    timeout=0.1
                )
                
                chunks_to_write.append(chunk)
                self._total_frames_written += len(chunk)
                
                # Write if we have enough chunks or enough time has passed
                current_time = time.time()
                if (len(chunks_to_write) >= 10 or 
                    current_time - last_write_time > 0.5):  # Write every 0.5 seconds max
                    
                    # Combine chunks and write
                    if chunks_to_write:
                        combined_chunk = np.concatenate(chunks_to_write, axis=0)
                        self._write_chunk_to_file(combined_chunk)  # Write synchronously for speed
                        chunks_to_write = []
                        last_write_time = current_time
                
                # Log progress every 30 seconds
                if self._start_time and self._total_frames_written % (self.config.samplerate * 30) == 0:
                    elapsed = time.time() - self._start_time
                    logger.info(f"Recording: {elapsed/60:.1f} minutes, {self._total_frames_written/self.config.samplerate:.1f}s of audio")
                    
            except asyncio.TimeoutError:
                # Write any remaining chunks on timeout
                if chunks_to_write:
                    combined_chunk = np.concatenate(chunks_to_write, axis=0)
                    self._write_chunk_to_file(combined_chunk)
                    chunks_to_write = []
                    last_write_time = time.time()
                continue
            except asyncio.CancelledError:
                # Write any remaining chunks before exiting
                if chunks_to_write:
                    combined_chunk = np.concatenate(chunks_to_write, axis=0)
                    self._write_chunk_to_file(combined_chunk)
                break
            except Exception as e:
                logger.error(f"Error in stream writer: {e}")
                self._state = RecordingState.ERROR
                break
    
    def _write_chunk_to_file(self, chunk: np.ndarray) -> None:
        """Write audio chunk to file (runs in thread executor)."""
        with self._write_lock:
            if self._file_writer:
                self._file_writer.write(chunk)
                self._file_writer.flush()  # Ensure data is written to disk
    
    async def _close_file_and_save_metadata(self, output_path: Path) -> None:
        """Close audio file and save metadata."""
        if not self._file_writer:
            logger.warning("No audio file to close")
            return
        
        # Close file
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._file_writer.close)
        self._file_writer = None
        
        duration_seconds = self._total_frames_written / self.config.samplerate
        
        # Save metadata
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": duration_seconds,
            "total_frames": self._total_frames_written,
            "device": self._device_info,
            "config": asdict(self.config),
            "audio_file": output_path.name
        }
        
        metadata_path = output_path.with_suffix('.json')
        try:
            await loop.run_in_executor(
                None,
                lambda: metadata_path.write_text(json.dumps(metadata, indent=2))
            )
        except Exception as e:
            # Log error but don't fail the recording
            logger.warning(f"Failed to save metadata: {e}")
        
        logger.info(f"Saved {duration_seconds:.2f} seconds of audio to {output_path}")
        logger.info(f"Metadata saved to {metadata_path}")
        
    def stop(self) -> None:
        """Stop the recording."""
        if self._state == RecordingState.RECORDING:
            self._state = RecordingState.STOPPING
            logger.info("Stopping recording")
        self._recording = False  # Keep for backward compatibility
        
    async def get_device_info(self, device: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """Get device info (for backward compatibility)."""
        device_obj = await DeviceManager.get_device_info(device)
        return asdict(device_obj)
    
    async def list_input_devices(self) -> List[Dict[str, Any]]:
        """List input devices (for backward compatibility)."""
        devices = await DeviceManager.list_input_devices()
        return [asdict(device) for device in devices]