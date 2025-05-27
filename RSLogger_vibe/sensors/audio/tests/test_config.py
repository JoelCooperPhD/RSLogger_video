import pytest
import json
from pathlib import Path
import tempfile

from src.recorder import RecordingConfig
from src.config import ConfigManager


class TestRecordingConfig:
    def test_default_values(self):
        config = RecordingConfig()
        assert config.samplerate == 44100
        assert config.channels == 1
        assert config.dtype == 'float32'
        assert config.output_dir == 'recordings'
        assert config.device is None
        
    def test_custom_values(self):
        config = RecordingConfig(
            samplerate=48000,
            channels=2,
            dtype='int16',
            output_dir='custom_dir',
            device=1
        )
        assert config.samplerate == 48000
        assert config.channels == 2
        assert config.dtype == 'int16'
        assert config.output_dir == 'custom_dir'
        assert config.device == 1


class TestConfigManager:
    def test_default_config_path(self):
        manager = ConfigManager()
        assert manager.config_path == Path.home() / ".rslogger" / "config.json"
        
    def test_custom_config_path(self):
        custom_path = Path("/tmp/test_config.json")
        manager = ConfigManager(custom_path)
        assert manager.config_path == custom_path
        
    def test_load_default_when_no_file(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        temp_path.unlink()  # Delete the file
        
        manager = ConfigManager(temp_path)
        config = manager.load()
        
        assert isinstance(config, RecordingConfig)
        assert config.samplerate == 44100
        assert config.channels == 1
        
    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
            
        try:
            manager = ConfigManager(temp_path)
            
            # Save custom config
            custom_config = RecordingConfig(
                samplerate=48000,
                channels=2,
                device="USB Mic"
            )
            manager.save(custom_config)
            
            # Load and verify
            loaded_config = manager.load()
            assert loaded_config.samplerate == 48000
            assert loaded_config.channels == 2
            assert loaded_config.device == "USB Mic"
            
        finally:
            temp_path.unlink()
            
    def test_update_partial_config(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
            
        try:
            manager = ConfigManager(temp_path)
            
            # Update only samplerate
            updated_config = manager.update(samplerate=96000)
            assert updated_config.samplerate == 96000
            assert updated_config.channels == 1  # Default unchanged
            
            # Update multiple fields
            updated_config = manager.update(
                channels=2,
                device=1
            )
            assert updated_config.samplerate == 96000  # Previous update retained
            assert updated_config.channels == 2
            assert updated_config.device == 1
            
        finally:
            temp_path.unlink()
            
    def test_reset_config(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
            
        try:
            manager = ConfigManager(temp_path)
            
            # Save custom config
            manager.save(RecordingConfig(samplerate=48000))
            assert temp_path.exists()
            
            # Reset
            manager.reset()
            assert not temp_path.exists()
            
            # Load should return defaults
            config = manager.load()
            assert config.samplerate == 44100
            
        finally:
            if temp_path.exists():
                temp_path.unlink()
                
    def test_invalid_json_fallback(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json{")
            temp_path = Path(f.name)
            
        try:
            manager = ConfigManager(temp_path)
            config = manager.load()
            
            # Should return defaults on invalid JSON
            assert config.samplerate == 44100
            
        finally:
            temp_path.unlink()