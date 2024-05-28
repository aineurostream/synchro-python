import unittest
from unittest.mock import MagicMock, patch
import pyaudio

from src.input_output.audio_stream_output import AudioStreamOutput


class TestAudioStreamOutput(unittest.TestCase):

    @patch('pyaudio.PyAudio')
    def test_start_output(self, mock_pyaudio):
        mock_device = MagicMock()
        mock_device.device_index = 1
        mock_device.name = 'Test Device'
        mock_stream = MagicMock()
        mock_pyaudio.return_value.open.return_value = mock_stream

        audio_output = AudioStreamOutput(mock_device)
        audio_output.start_output()

        mock_pyaudio.return_value.open.assert_called_once_with(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            output=True,
            output_device_index=1
        )
        self.assertIsNotNone(audio_output.stream)

    @patch('pyaudio.PyAudio')
    def test_write_audio_frames(self, mock_pyaudio):
        mock_device = MagicMock()
        mock_stream = MagicMock()
        mock_pyaudio.return_value.open.return_value = mock_stream

        audio_output = AudioStreamOutput(mock_device)
        audio_output.stream = mock_stream
        audio_frames = b'audio_data'

        audio_output.write_audio_frames(audio_frames)

        mock_stream.write.assert_called_once_with(audio_frames)

    @patch('pyaudio.PyAudio')
    def test_stop_output(self, mock_pyaudio):
        mock_device = MagicMock()
        mock_stream = MagicMock()
        mock_pyaudio.return_value.open.return_value = mock_stream

        audio_output = AudioStreamOutput(mock_device)
        audio_output.stream = mock_stream

        audio_output.stop_output()

        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_pyaudio.return_value.terminate.assert_called_once()

    @patch('pyaudio.PyAudio')
    def test_start_output_error(self, mock_pyaudio):
        mock_device = MagicMock()
        mock_pyaudio.return_value.open.side_effect = Exception('Test Error')

        with self.assertLogs('utils.logger', level='ERROR') as cm:
            audio_output = AudioStreamOutput(mock_device)
            audio_output.start_output()

        self.assertIn(
            f'Error when outputting an audio stream to the {mock_device.name}: Test Error', cm.output[0])
        self.assertIsNone(audio_output.stream)
