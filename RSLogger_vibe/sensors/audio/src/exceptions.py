"""Custom exceptions for RSLogger Audio."""


class RecorderError(Exception):
    """Base exception for recorder errors."""
    pass


class DeviceNotFoundError(RecorderError):
    """Raised when audio device is not found."""
    pass


class RecordingError(RecorderError):
    """Raised when recording fails."""
    pass


class ConfigurationError(RecorderError):
    """Raised when configuration is invalid."""
    pass