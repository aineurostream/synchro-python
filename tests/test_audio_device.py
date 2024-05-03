import unittest
from src.models.audio_device import AudioDevice

class TestAudioDevice(unittest.TestCase):

    def test_audio_device_init(self):
        device_index = 1
        device_info = {
            'name': 'Test Device',
            'maxInputChannels': 2,
            'maxOutputChannels': 4
        }
        device = AudioDevice(device_index, device_info)

        self.assertEqual(device.device_index, device_index)
        self.assertEqual(device.device_info, device_info)
        self.assertTrue(device.is_input)
        self.assertTrue(device.is_output)
        self.assertEqual(device.name, 'Test Device')

    def test_audio_device_no_input(self):
        device_index = 2
        device_info = {
            'name': 'Output Device',
            'maxInputChannels': 0,
            'maxOutputChannels': 2
        }
        device = AudioDevice(device_index, device_info)

        self.assertFalse(device.is_input)
        self.assertTrue(device.is_output)

    def test_audio_device_no_output(self):
        device_index = 3
        device_info = {
            'name': 'Input Device',
            'maxInputChannels': 1,
            'maxOutputChannels': 0
        }
        device = AudioDevice(device_index, device_info)

        self.assertTrue(device.is_input)
        self.assertFalse(device.is_output)

    def test_audio_device_str_representation(self):
        device_index = 4
        device_info = {
            'name': 'Test Device 2',
            'maxInputChannels': 1,
            'maxOutputChannels': 2
        }
        device = AudioDevice(device_index, device_info)

        expected_str = 'Audio device: Test Device 2 (Input: True, Output: True)'
        self.assertEqual(str(device), expected_str)
