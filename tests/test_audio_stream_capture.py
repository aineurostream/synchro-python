import unittest
from unittest.mock import MagicMock, patch
import pyaudio

from src.input_output.audio_stream_capture import AudioStreamCapture


class TestAudioStreamCapture(unittest.TestCase):

    @patch('pyaudio.PyAudio')
    def test_start_capture(self, mock_pyaudio):
        mock_device = MagicMock()
        mock_device.device_index = 1
        mock_device.name = 'Test Device'
        mock_stream = MagicMock()
        mock_pyaudio.return_value.open.return_value = mock_stream

        audio_capture = AudioStreamCapture(mock_device)
        audio_capture.start_capture()

        mock_pyaudio.return_value.open.assert_called_once_with(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            input_device_index=1,
            frames_per_buffer=1024
        )
        self.assertIsNotNone(audio_capture.stream)

    @patch('pyaudio.PyAudio')
    def test_get_audio_frames(self, mock_pyaudio):
        mock_device = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b'audio_data'
        mock_pyaudio.return_value.open.return_value = mock_stream

        audio_capture = AudioStreamCapture(mock_device)
        audio_capture.stream = mock_stream

        audio_frames = audio_capture.get_audio_frames()

        self.assertEqual(audio_frames, b'audio_data')

    @patch('pyaudio.PyAudio')
    def test_stop_capture(self, mock_pyaudio):
        mock_device = MagicMock()
        mock_stream = MagicMock()
        mock_pyaudio.return_value.open.return_value = mock_stream

        audio_capture = AudioStreamCapture(mock_device)
        audio_capture.stream = mock_stream

        audio_capture.stop_capture()

        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_pyaudio.return_value.terminate.assert_called_once()

    @patch('pyaudio.PyAudio')
    def test_start_capture_error(self, mock_pyaudio):
        mock_device = MagicMock()
        mock_device.name = 'Test Device'
        mock_pyaudio.return_value.open.side_effect = Exception('Test Error')

        with self.assertLogs('utils.logger', level='ERROR') as cm:
            audio_capture = AudioStreamCapture(mock_device)
            audio_capture.start_capture()

        self.assertIn(
            f'Error when capturing an audio stream from the {mock_device.name}: Test Error', cm.output[0])
        self.assertIsNone(audio_capture.stream)
