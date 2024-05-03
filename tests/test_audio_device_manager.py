import unittest
from unittest.mock import patch, MagicMock
import pyaudio
from src.modules.audio_device_manager import get_audio_devices, test_audio_device
from src.models.audio_device import AudioDevice

class TestAudioDeviceManager(unittest.TestCase):

    @patch('pyaudio.PyAudio')
    def test_get_audio_devices(self, mock_pyaudio):
        mock_audio = mock_pyaudio.return_value
        mock_audio.get_device_count.return_value = 2
        mock_audio.get_device_info_by_index.side_effect = [
            {'name': 'Device 1', 'maxInputChannels': 1, 'maxOutputChannels': 0},
            {'name': 'Device 2', 'maxInputChannels': 0, 'maxOutputChannels': 2}
        ]

        devices = get_audio_devices()

        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0].name, 'Device 1')
        self.assertTrue(devices[0].is_input)
        self.assertFalse(devices[0].is_output)
        self.assertEqual(devices[1].name, 'Device 2')
        self.assertFalse(devices[1].is_input)
        self.assertTrue(devices[1].is_output)
        mock_audio.terminate.assert_called_once()

    @patch('pyaudio.PyAudio')
    def test_test_audio_device_input(self, mock_pyaudio):
        mock_audio = mock_pyaudio.return_value
        mock_stream = MagicMock()
        mock_audio.open.return_value = mock_stream
        device = AudioDevice(0, {'name': 'Input Device', 'maxInputChannels': 1, 'maxOutputChannels': 0})

        test_audio_device(device)

        mock_audio.open.assert_called_once_with(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            input_device_index=0
        )
        mock_audio.terminate.assert_called_once()

    @patch('pyaudio.PyAudio')
    def test_test_audio_device_output(self, mock_pyaudio):
        mock_audio = mock_pyaudio.return_value
        mock_stream = MagicMock()
        mock_audio.open.return_value = mock_stream
        device = AudioDevice(1, {'name': 'Output Device', 'maxInputChannels': 0, 'maxOutputChannels': 2})

        test_audio_device(device)

        mock_audio.open.assert_called_once_with(
            format=pyaudio.paInt16,
            channels=1,
            rate=4100,
            output=True,
            output_device_index=1
        )
        mock_audio.terminate.assert_called_once()
