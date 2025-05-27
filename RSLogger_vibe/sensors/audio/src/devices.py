"""Device management module for RSLogger Audio."""

import asyncio
import sounddevice as sd
from typing import Optional, Union, List, Dict, Any
from dataclasses import dataclass

from .exceptions import DeviceNotFoundError


@dataclass
class AudioDevice:
    """Represents an audio device."""
    id: Optional[int]
    name: str
    channels: int
    samplerate: float
    
    @classmethod
    def from_dict(cls, device_dict: Dict[str, Any]) -> 'AudioDevice':
        """Create AudioDevice from dictionary."""
        return cls(
            id=device_dict.get('id'),
            name=device_dict['name'],
            channels=device_dict['channels'],
            samplerate=device_dict['samplerate']
        )


class DeviceManager:
    """Manages audio device operations."""
    
    @staticmethod
    async def get_device_info(device: Optional[Union[int, str]] = None) -> AudioDevice:
        """Get information about a specific audio device."""
        loop = asyncio.get_event_loop()
        
        try:
            device_info = await loop.run_in_executor(
                None,
                sd.query_devices,
                device,
                'input'
            )
        except Exception as e:
            raise DeviceNotFoundError(f"Failed to query device {device}: {e}") from e
        
        # Get device index if device was specified by name
        device_id = device if isinstance(device, int) else None
        if device is None or isinstance(device, str):
            all_devices = await loop.run_in_executor(None, sd.query_devices)
            for idx, dev in enumerate(all_devices):
                if dev['name'] == device_info['name']:
                    device_id = idx
                    break
        
        return AudioDevice(
            id=device_id,
            name=device_info['name'],
            channels=device_info['max_input_channels'],
            samplerate=device_info['default_samplerate']
        )
    
    @staticmethod
    async def list_input_devices() -> List[AudioDevice]:
        """List all available input devices."""
        loop = asyncio.get_event_loop()
        
        try:
            devices = await loop.run_in_executor(None, sd.query_devices)
        except Exception as e:
            raise DeviceNotFoundError(f"Failed to query devices: {e}") from e
        
        input_devices = []
        for idx, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append(AudioDevice(
                    id=idx,
                    name=device['name'],
                    channels=device['max_input_channels'],
                    samplerate=device['default_samplerate']
                ))
                
        return input_devices
    
    @staticmethod
    def get_default_device() -> Optional[Union[int, str]]:
        """Get the default input device."""
        try:
            default_device = sd.query_devices(kind='input')
            return default_device['name']
        except Exception:
            return None