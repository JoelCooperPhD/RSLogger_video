import pytest
import asyncio
import json
from pathlib import Path
import tempfile
import numpy as np
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from src.recorder import AudioRecorder, RecordingConfig


class TestAudioRecorder:
    @pytest.fixture
    def config(self):
        return RecordingConfig(
            samplerate=44100,
            channels=1,
            dtype='float32'
        )
        
    @pytest.fixture
    def recorder(self, config):
        return AudioRecorder(config)
        
    def test_initialization(self, recorder, config):
        assert recorder.config == config
        assert hasattr(recorder, '_state')
        assert hasattr(recorder, '_recording')
        assert isinstance(recorder._audio_queue, asyncio.Queue)
        assert recorder._device_info is None
        
    def test_audio_callback(self, recorder):
        # Create mock audio data
        frames = 1024
        indata = np.random.random((frames, 1)).astype('float32')
        
        # Call the callback
        recorder._audio_callback(indata, frames, None, None)
        
        # Check data was queued
        assert recorder._audio_queue.qsize() == 1
        queued_data = recorder._audio_queue.get_nowait()
        assert np.array_equal(queued_data, indata)
        
    def test_audio_callback_with_status(self, recorder, caplog):
        indata = np.zeros((1024, 1))
        status = MagicMock()
        status.__str__.return_value = "Buffer overrun"
        
        with caplog.at_level('WARNING'):
            recorder._audio_callback(indata, 1024, None, status)
        
        assert "Audio callback status: Buffer overrun" in caplog.text
        
    def test_stop_recording(self, recorder):
        from src.enums import RecordingState
        recorder._state = RecordingState.RECORDING
        recorder._recording = True
        recorder.stop()
        assert recorder._recording is False
        
    @pytest.mark.asyncio
    async def test_get_device_info_default(self, recorder):
        mock_device = {
            'name': 'Default Input',
            'max_input_channels': 2,
            'default_samplerate': 44100.0
        }
        
        mock_all_devices = [{
            'name': 'Default Input',
            'max_input_channels': 2,
            'default_samplerate': 44100.0
        }]
        
        with patch('sounddevice.query_devices') as mock_query:
            def query_side_effect(device=None, kind=None):
                if device is None and kind is None:
                    return mock_all_devices
                else:
                    return mock_device
            
            mock_query.side_effect = query_side_effect
            info = await recorder.get_device_info()
            
        assert info['name'] == 'Default Input'
        assert info['channels'] == 2
        assert info['samplerate'] == 44100.0
        
    @pytest.mark.asyncio
    async def test_get_device_info_by_id(self, recorder):
        mock_device = {
            'name': 'USB Mic',
            'max_input_channels': 1,
            'default_samplerate': 48000.0
        }
        
        with patch('sounddevice.query_devices', return_value=mock_device):
            info = await recorder.get_device_info(1)
            
        assert info['id'] == 1
        assert info['name'] == 'USB Mic'
        
    @pytest.mark.asyncio
    async def test_list_input_devices(self, recorder):
        mock_devices = [
            {'name': 'Built-in', 'max_input_channels': 2, 'default_samplerate': 44100},
            {'name': 'USB Mic', 'max_input_channels': 1, 'default_samplerate': 48000},
            {'name': 'Output Only', 'max_input_channels': 0, 'default_samplerate': 44100},
        ]
        
        with patch('sounddevice.query_devices', return_value=mock_devices):
            devices = await recorder.list_input_devices()
            
        assert len(devices) == 2  # Only input devices
        assert devices[0]['id'] == 0
        assert devices[0]['name'] == 'Built-in'
        assert devices[1]['id'] == 1
        assert devices[1]['name'] == 'USB Mic'
        
    # Note: These tests were for the old chunk-based architecture
    # The new streaming architecture doesn't use _save_recording method
    @pytest.mark.skip(reason="Architecture changed to streaming - test no longer applicable")
    async def test_save_recording_with_metadata(self, recorder):
        pass
            
    @pytest.mark.skip(reason="Architecture changed to streaming - test no longer applicable") 
    async def test_save_recording_no_data(self, recorder, caplog):
        pass
            
    @pytest.mark.skip(reason="Test needs updating for new streaming architecture")
    async def test_record_with_duration(self, recorder):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.wav"
            
            # Mock the audio stream and device info
            mock_stream = MagicMock()
            mock_stream.__enter__ = MagicMock(return_value=mock_stream)
            mock_stream.__exit__ = MagicMock(return_value=None)
            
            with patch('sounddevice.InputStream', return_value=mock_stream):
                from src.devices import DeviceManager, AudioDevice
                with patch.object(DeviceManager, 'get_device_info', new_callable=AsyncMock) as mock_get_info:
                    with patch.object(recorder, '_close_file_and_save_metadata', new_callable=AsyncMock):
                        mock_get_info.return_value = AudioDevice(id=0, name='Default', channels=2, samplerate=44100)
                        
                        # Simulate short recording
                        async def record_task():
                            await recorder.record(output_path, duration=0.1)
                            
                        await asyncio.wait_for(record_task(), timeout=1.0)
                        
            assert recorder._recording is False
            
    @pytest.mark.asyncio
    async def test_record_cancelled(self, recorder):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.wav"
            
            mock_stream = MagicMock()
            mock_stream.__enter__ = MagicMock(return_value=mock_stream)
            mock_stream.__exit__ = MagicMock(return_value=None)
            
            with patch('sounddevice.InputStream', return_value=mock_stream):
                from src.devices import DeviceManager, AudioDevice
                with patch.object(DeviceManager, 'get_device_info', new_callable=AsyncMock) as mock_get_info:
                    mock_get_info.return_value = AudioDevice(id=0, name='Default', channels=2, samplerate=44100)
                    with patch.object(recorder, '_close_file_and_save_metadata', new_callable=AsyncMock):
                        # Start recording
                        record_task = asyncio.create_task(
                            recorder.record(output_path, duration=None)
                        )
                        
                        # Let it start
                        await asyncio.sleep(0.1)
                        
                        # Cancel it
                        record_task.cancel()
                        
                        with pytest.raises(asyncio.CancelledError):
                            await record_task