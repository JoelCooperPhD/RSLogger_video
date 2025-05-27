import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import asdict

from .recorder import RecordingConfig


class ConfigManager:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".rslogger" / "config.json"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
    def load(self) -> RecordingConfig:
        """Load configuration from file, return defaults if not found."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                return RecordingConfig(**data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Warning: Invalid config file, using defaults. Error: {e}")
                
        return RecordingConfig()
    
    def save(self, config: RecordingConfig) -> None:
        """Save configuration to file."""
        with open(self.config_path, 'w') as f:
            json.dump(asdict(config), f, indent=2)
            
    def update(self, **kwargs) -> RecordingConfig:
        """Update specific configuration values."""
        config = self.load()
        for key, value in kwargs.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)
        self.save(config)
        return config
    
    def reset(self) -> None:
        """Reset configuration to defaults."""
        if self.config_path.exists():
            self.config_path.unlink()