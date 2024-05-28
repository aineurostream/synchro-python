import unittest
from unittest.mock import patch, MagicMock
import pyaudio

from src.input_output.audio_device_manager import get_audio_devices, test_audio_device
from src.modules.audio_device import AudioDevice


class TestAudioDeviceManager(unittest.TestCase):

    @patch('pyaudio.PyAudio')
    def test_get_audio_devices(self, mock_pyaudio):
        mock_device_info_1 = {'name': 'Device 1', 'hostApi': 0,
                              'maxInputChannels': 1, 'maxOutputChannels': 0}
        mock_device_info_2 = {'name': 'Device 2', 'hostApi': 0,
                              'maxInputChannels': 0, 'maxOutputChannels': 1}
        mock_pyaudio.return_value.get_device_info_by_index.side_effect = [
            mock_device_info_1, mock_device_info_2]
        mock_pyaudio.return_value.get_device_count.return_value = 2

        devices = get_audio_devices()

        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0].name, 'Device 1')
        self.assertTrue(devices[0].is_input)
        self.assertFalse(devices[0].is_output)
        self.assertEqual(devices[1].name, 'Device 2')
        self.assertFalse(devices[1].is_input)
        self.assertTrue(devices[1].is_output)

    @patch('pyaudio.PyAudio')
    def test_test_audio_device(self, mock_pyaudio):
        mock_device_1 = AudioDevice(
            0, {'name': 'Device 1', 'hostApi': 0, 'maxInputChannels': 1, 'maxOutputChannels': 0})
        mock_device_2 = AudioDevice(
            1, {'name': 'Device 2', 'hostApi': 0, 'maxInputChannels': 0, 'maxOutputChannels': 1})
        devices = [mock_device_1, mock_device_2]

        mock_stream_1 = MagicMock()
        mock_stream_2 = MagicMock()
        mock_pyaudio.return_value.open.side_effect = [
            mock_stream_1, mock_stream_2]

        test_audio_device(devices)

        mock_pyaudio.return_value.open.assert_any_call(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            input_device_index=0
        )
        mock_pyaudio.return_value.open.assert_any_call(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            output=True,
            output_device_index=1
        )

    @patch('pyaudio.PyAudio')
    def test_test_audio_device_error(self, mock_pyaudio):
        mock_device = AudioDevice(
            0, {'name': 'Device', 'hostApi': 0, 'maxInputChannels': 1, 'maxOutputChannels': 1})
        devices = [mock_device]

        mock_pyaudio.return_value.open.side_effect = Exception('Test Error')

        with self.assertLogs('utils.logger', level='ERROR') as cm:
            test_audio_device(devices)

        self.assertIn(
            f"Opening error {mock_device.name}: Test Error", cm.output[0])
