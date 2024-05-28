import unittest
from unittest.mock import patch, MagicMock
from src.modules.audio_device import AudioDevice


class TestAudioDevice(unittest.TestCase):

    def test_input_output_device(self):
        device_info = {
            "maxInputChannels": 2,
            "maxOutputChannels": 2,
            "name": "Test Audio Device"
        }
        device_index = 0
        audio_device = AudioDevice(device_index, device_info)
        self.assertTrue(audio_device.is_input)
        self.assertTrue(audio_device.is_output)
        self.assertEqual(audio_device.name, "Test Audio Device")

    def test_input_only_device(self):
        device_info = {
            "maxInputChannels": 1,
            "maxOutputChannels": 0,
            "name": "Input Only Device"
        }
        device_index = 1
        audio_device = AudioDevice(device_index, device_info)
        self.assertTrue(audio_device.is_input)
        self.assertFalse(audio_device.is_output)
        self.assertEqual(audio_device.name, "Input Only Device")

    def test_output_only_device(self):
        device_info = {
            "maxInputChannels": 0,
            "maxOutputChannels": 2,
            "name": "Output Only Device"
        }
        device_index = 2
        audio_device = AudioDevice(device_index, device_info)
        self.assertFalse(audio_device.is_input)
        self.assertTrue(audio_device.is_output)
        self.assertEqual(audio_device.name, "Output Only Device")

    def test_no_input_output_device(self):
        device_info = {
            "maxInputChannels": 0,
            "maxOutputChannels": 0,
            "name": "No I/O Device"
        }
        device_index = 3
        audio_device = AudioDevice(device_index, device_info)
        self.assertFalse(audio_device.is_input)
        self.assertFalse(audio_device.is_output)
        self.assertEqual(audio_device.name, "No I/O Device")

    @patch('src.modules.audio_device.log')
    def test_str_representation(self, mock_log):
        device_info = {
            "maxInputChannels": 1,
            "maxOutputChannels": 1,
            "name": "Test Device"
        }
        device_index = 4
        audio_device = AudioDevice(device_index, device_info)
        expected_str = "Audio device: Test Device (Input: True, Output: True)"
        self.assertEqual(str(audio_device), expected_str)
        mock_log.assert_called_with(expected_str)
