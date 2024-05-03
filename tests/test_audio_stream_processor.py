import unittest
from unittest.mock import patch, MagicMock
import wave
from src.modules.audio_stream_processor import process_audio_stream

class TestAudioStreamProcessor(unittest.TestCase):

    @patch('wave.open')
    def test_process_audio_stream_with_format_channels_rate(self, mock_wave_open):
        mock_wave_file = MagicMock()
        mock_wave_open.return_value.__enter__.return_value = mock_wave_file
        data = b'audio_data'
        format = wave.WAVE_FORMAT_PCM
        channels = 2
        rate = 44100

        result = process_audio_stream(data, format, channels, rate)

        mock_wave_file.setparams.assert_called_once_with((channels, format, rate, 0, 'NONE', 'not compressed'))
        mock_wave_file.writeframes.assert_called_once_with(data)
        self.assertEqual(result, data)

    def test_process_audio_stream_without_format_channels_rate(self):
        data = b'audio_data'

        result = process_audio_stream(data)

        self.assertEqual(result, data)

    @patch('wave.open')
    def test_process_audio_stream_with_wave_file_error(self, mock_wave_open):
        mock_wave_open.side_effect = Exception('Wave file error')
        data = b'audio_data'
        format = wave.WAVE_FORMAT_PCM
        channels = 2
        rate = 44100

        result = process_audio_stream(data, format, channels, rate)

        self.assertEqual(result, data)
