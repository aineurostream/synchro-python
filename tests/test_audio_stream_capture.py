import unittest
from unittest.mock import patch, MagicMock
import pyaudio
import wave
from src.modules.audio_stream_capture import capture_audio_stream
from src.models.audio_device import AudioDevice

class TestAudioStreamCapture(unittest.TestCase):

    @patch('pyaudio.PyAudio')
    def test_capture_audio_stream(self, mock_pyaudio):
        mock_audio = mock_pyaudio.return_value
        mock_stream = MagicMock()
        mock_audio.open.return_value = mock_stream
        mock_stream.read.side_effect = [b'data1', b'data2', b'data3']
        device = AudioDevice(0, {'name': 'Test Device', 'maxInputChannels': 1, 'maxOutputChannels': 0})
        output_file = 'test_output.wav'

        capture_audio_stream(device, output_file, duration=1, chunk=1024, format=pyaudio.paInt16, channels=1, rate=44100)

        mock_audio.open.assert_called_once_with(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            input_device_index=0,
            frames_per_buffer=None
        )
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_audio.terminate.assert_called_once()

        with wave.open(output_file, 'rb') as wave_file:
            self.assertEqual(wave_file.getnchannels(), 1)
            self.assertEqual(wave_file.getsampwidth(), mock_audio.get_sample_size(pyaudio.paInt16))
            self.assertEqual(wave_file.getframerate(), 44100)
            self.assertEqual(wave_file.readframes(wave_file.getnframes()), b'data1data2data3')

    @patch('pyaudio.PyAudio')
    def test_capture_audio_stream_with_frames_per_buffer(self, mock_pyaudio):
        mock_audio = mock_pyaudio.return_value
        mock_stream = MagicMock()
        mock_audio.open.return_value = mock_stream
        mock_stream.read.side_effect = [b'data1', b'data2', b'data3']
        device = AudioDevice(0, {'name': 'Test Device', 'maxInputChannels': 1, 'maxOutputChannels': 0})
        output_file = 'test_output.wav'
        frames_per_buffer = 512

        capture_audio_stream(device, output_file, duration=1, chunk=1024, format=pyaudio.paInt16, channels=1, rate=44100, frames_per_buffer=frames_per_buffer)

        mock_audio.open.assert_called_once_with(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            input_device_index=0,
            frames_per_buffer=frames_per_buffer
        )
