import unittest
from unittest.mock import patch, MagicMock
import pyaudio
import wave
from src.main import capture_audio_stream, output_audio_stream
from src.modules.audio_device_manager import get_audio_devices
from src.models.audio_device import AudioDevice

class TestMain(unittest.TestCase):

    @patch('src.modules.audio_device_manager.get_audio_devices')
    def test_capture_audio_stream(self, mock_get_audio_devices):
        mock_input_device = AudioDevice(0, {'name': 'Input Device', 'maxInputChannels': 1, 'maxOutputChannels': 0})
        mock_get_audio_devices.return_value = [mock_input_device]

        with patch('wave.open') as mock_wave_open:
            mock_wave_file = MagicMock()
            mock_wave_open.return_value = mock_wave_file:
                with patch('pyaudio.PyAudio') as mock_pyaudio:
                    mock_audio = mock_pyaudio.return_value
                    mock_stream = MagicMock()
                    mock_audio.open.return_value = mock_stream

                    capture_audio_stream(mock_input_device, output_file="test_output.wav", duration=5)

                    mock_audio.open.assert_called_once_with(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=44100,
                        input=True,
                        input_device_index=0
                    )
                    mock_stream.start_stream.assert_called_once()
                    mock_wave_file.setnchannels.assert_called_once_with(1)
                    mock_wave_file.setsampwidth.assert_called_once_with(pyaudio.get_sample_size(pyaudio.paInt16))
                    mock_wave_file.setframerate.assert_called_once_with(44100)
                    mock_stream.stop_stream.assert_called_once()
                    mock_stream.close.assert_called_once()
                    mock_audio.terminate.assert_called_once()

    @patch('src.modules.audio_device_manager.get_audio_devices')
    def test_output_audio_stream(self, mock_get_audio_devices):
        mock_output_device = AudioDevice(1, {'name': 'Output Device', 'maxInputChannels': 0, 'maxOutputChannels': 2})
        mock_get_audio_devices.return_value = [mock_output_device]

        with patch('wave.open') as mock_wave_open:
            mock_wave_file = MagicMock()
            mock_wave_file.getnchannels.return_value = 1
            mock_wave_file.getsampwidth.return_value = pyaudio.get_sample_size(pyaudio.paInt16)
            mock_wave_file.getframerate.return_value = 44100
            mock_wave_open.return_value = mock_wave_file:
                with patch('pyaudio.PyAudio') as mock_pyaudio:
                    mock_audio = mock_pyaudio.return_value
                    mock_stream = MagicMock()
                    mock_audio.open.return_value = mock_stream

                    output_audio_stream(mock_output_device, input_file="test_input.wav")

                    mock_audio.open.assert_called_once_with(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=44100,
                        output=True,
                        output_device_index=1
                    )
                    mock_stream.start_stream.assert_called_once()
                    mock_stream.stop_stream.assert_called_once()
                    mock_stream.close.assert_called_once()
                    mock_audio.terminate.assert_called_once()
