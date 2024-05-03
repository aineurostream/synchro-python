import unittest
from unittest.mock import patch, MagicMock
import pyaudio
import wave
from src.modules.audio_stream_output import output_audio_stream
from src.models.audio_device import AudioDevice

class TestAudioStreamOutput(unittest.TestCase):

    @patch('pyaudio.PyAudio')
    def test_output_audio_stream(self, mock_pyaudio):
        mock_audio = mock_pyaudio.return_value
        mock_stream = MagicMock()
        mock_audio.open.return_value = mock_stream
        device = AudioDevice(1, {'name': 'Output Device', 'maxInputChannels': 0, 'maxOutputChannels': 2})
        input_file = 'test_input.wav'
        chunk = 1024

        output_audio_stream(device, input_file, chunk=chunk)

        mock_audio.open.assert_called_once_with(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            output=True,
            output_device_index=1
        )
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_audio.terminate.assert_called_once()

    @patch('pyaudio.PyAudio')
    def test_output_audio_stream_with_custom_format_and_channels(self, mock_pyaudio):
        mock_audio = mock_pyaudio.return_value
        mock_stream = MagicMock()
        mock_audio.open.return_value = mock_stream
        device = AudioDevice(1, {'name': 'Output Device', 'maxInputChannels': 0, 'maxOutputChannels': 2})
        input_file = 'test_input.wav'
        chunk = 1024
        format = pyaudio.paFloat32
        channels = 2

        output_audio_stream(device, input_file, chunk=chunk, format=format, channels=channels)

        mock_audio.open.assert_called_once_with(
            format=format,
            channels=channels,
            rate=44100,
            output=True,
            output_device_index=1
        )

    @patch('pyaudio.PyAudio')
    @patch('wave.open')
    def test_output_audio_stream_with_wave_file_error(self, mock_wave_open, mock_pyaudio):
        mock_audio = mock_pyaudio.return_value
        mock_stream = MagicMock()
        mock_audio.open.return_value = mock_stream
        mock_wave_open.side_effect = Exception('Wave file error')
        device = AudioDevice(1, {'name': 'Output Device', 'maxInputChannels': 0, 'maxOutputChannels': 2})
        input_file = 'test_input.wav'
        chunk = 1024

        output_audio_stream(device, input_file, chunk=chunk)

        mock_audio.open.assert_called_once_with(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            output=True,
            output_device_index=1
        )
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_audio.terminate.assert_called_once()
