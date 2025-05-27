"""Enumerations for RSLogger Audio."""

from enum import Enum, auto


class AudioFormat(str, Enum):
    """Supported audio data formats."""
    FLOAT32 = 'float32'
    INT16 = 'int16'
    INT32 = 'int32'
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid audio format."""
        return value in cls._value2member_map_


class RecordingState(Enum):
    """States of the audio recorder."""
    IDLE = auto()
    RECORDING = auto()
    STOPPING = auto()
    ERROR = auto()