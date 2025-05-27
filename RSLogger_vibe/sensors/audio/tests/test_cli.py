import pytest
import asyncio
from pathlib import Path
import tempfile
import sys
from unittest.mock import patch, AsyncMock, MagicMock

from main import main
from src.modes import handle_recording


class TestCLI:
    @pytest.mark.asyncio
    async def test_show_config(self, capsys):
        with patch('sys.argv', ['main.py', '--show-config']):
            with patch('src.config.ConfigManager.load') as mock_load:
                from src.recorder import RecordingConfig
                mock_load.return_value = RecordingConfig()
                
                await main()
                
        captured = capsys.readouterr()
        assert "Current configuration:" in captured.out
        assert "Sample rate: 44100 Hz" in captured.out
        assert "Channels: 1" in captured.out
        
    @pytest.mark.asyncio
    async def test_reset_config(self, capsys):
        with patch('sys.argv', ['main.py', '--reset-config']):
            with patch('src.config.ConfigManager.reset') as mock_reset:
                await main()
                
                mock_reset.assert_called_once()
                
        captured = capsys.readouterr()
        assert "Configuration reset to defaults" in captured.out
        
    @pytest.mark.asyncio
    async def test_save_config(self, capsys):
        with patch('sys.argv', ['main.py', '--samplerate', '48000', '--save-config']):
            with patch('src.config.ConfigManager.save') as mock_save:
                await main()
                
                # Verify save was called with correct config
                saved_config = mock_save.call_args[0][0]
                assert saved_config.samplerate == 48000
                
    @pytest.mark.asyncio
    async def test_list_devices(self, capsys):
        mock_devices = [
            {'id': 0, 'name': 'Built-in Mic', 'channels': 2, 'samplerate': 44100},
            {'id': 1, 'name': 'USB Mic', 'channels': 1, 'samplerate': 48000}
        ]
        
        from src.devices import AudioDevice
        mock_device_objs = [
            AudioDevice(id=0, name='Built-in Mic', channels=2, samplerate=44100),
            AudioDevice(id=1, name='USB Mic', channels=1, samplerate=48000)
        ]
        
        with patch('sys.argv', ['main.py', '--list-devices']):
            with patch('src.devices.DeviceManager.list_input_devices', new_callable=AsyncMock) as mock_list:
                mock_list.return_value = mock_device_objs
                
                await main()
                
        captured = capsys.readouterr()
        assert "Available input devices:" in captured.out
        assert "0: Built-in Mic (2 ch, 44100 Hz)" in captured.out
        assert "1: USB Mic (1 ch, 48000 Hz)" in captured.out
        
    @pytest.mark.asyncio
    async def test_device_info(self, capsys):
        mock_info = {
            'id': 1,
            'name': 'USB Mic',
            'channels': 2,
            'samplerate': 48000.0
        }
        
        from src.devices import AudioDevice
        mock_device_obj = AudioDevice(
            id=1,
            name='USB Mic',
            channels=2,
            samplerate=48000.0
        )
        
        with patch('sys.argv', ['main.py', '--device', '1', '--info']):
            with patch('src.devices.DeviceManager.get_device_info', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_device_obj
                
                await main()
                
        captured = capsys.readouterr()
        assert "Device 1:" in captured.out
        assert "Name: USB Mic" in captured.out
        assert "Max channels: 2" in captured.out
        
    @pytest.mark.asyncio
    async def test_record_with_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('sys.argv', ['main.py', 'test_recording.wav']):
                with patch('src.recorder.AudioRecorder.record', new_callable=AsyncMock) as mock_record:
                    with patch('pathlib.Path.mkdir'):
                        await main()
                        
                        # Verify record was called with correct path
                        call_args = mock_record.call_args[0]
                        assert call_args[0].name == 'test_recording.wav'
                        
    @pytest.mark.asyncio
    async def test_record_with_duration(self):
        with patch('sys.argv', ['main.py', '--duration', '5']):
            with patch('src.recorder.AudioRecorder.record', new_callable=AsyncMock) as mock_record:
                with patch('pathlib.Path.mkdir'):
                    await main()
                    
                    # Verify duration was passed
                    call_args = mock_record.call_args[0]
                    assert call_args[1] == 5.0
                    
    @pytest.mark.asyncio
    async def test_record_with_device(self):
        with patch('sys.argv', ['main.py', '--device', '2', '-d', '5']):
            with patch('src.recorder.AudioRecorder') as MockRecorder:
                mock_instance = MockRecorder.return_value
                mock_instance.record = AsyncMock()
                from src.devices import AudioDevice
                with patch('src.devices.DeviceManager.get_device_info', new_callable=AsyncMock) as mock_get:
                    mock_get.return_value = AudioDevice(id=2, name='USB Device', channels=2, samplerate=48000)
                
                with patch('pathlib.Path.mkdir'):
                    await main()
                    
                    # Verify recorder was created with device=2
                    config = MockRecorder.call_args[0][0]
                    assert config.device == 2
                    
    @pytest.mark.asyncio
    async def test_handle_recording_interrupt(self):
        recorder = MagicMock()
        recorder.record = AsyncMock()
        
        output_path = Path("test.wav")
        
        # Simulate Ctrl+C during recording
        async def interrupt_recording(*args, **kwargs):
            await asyncio.sleep(0.1)
            recorder.stop()
            raise asyncio.CancelledError()
            
        recorder.record.side_effect = interrupt_recording
        
        try:
            await handle_recording(recorder, output_path, None)
        except asyncio.CancelledError:
            pass
        
        recorder.stop.assert_called()
        
    @pytest.mark.asyncio
    async def test_filename_generation_with_device(self):
        with patch('sys.argv', ['main.py', '--device', '1', '-d', '5']):
            with patch('src.recorder.AudioRecorder') as MockRecorder:
                mock_instance = MockRecorder.return_value
                mock_instance.record = AsyncMock()
                from src.devices import AudioDevice
                with patch('src.devices.DeviceManager.get_device_info', new_callable=AsyncMock) as mock_get:
                    mock_get.return_value = AudioDevice(id=1, name='USB Mic', channels=2, samplerate=48000)
                mock_instance.list_input_devices = AsyncMock(return_value=[])
                
                with patch('pathlib.Path.mkdir'):
                    with patch('datetime.datetime') as mock_datetime:
                        mock_datetime.now.return_value.strftime.return_value = "20250123_143052"
                        
                        await main()
                        
                        # Verify filename includes device ID
                        call_args = mock_instance.record.call_args[0]
                        assert "device1" in str(call_args[0])