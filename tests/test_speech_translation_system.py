import unittest
from unittest.mock import patch, MagicMock
from src.input_output.audio_device_manager import get_audio_devices
from src.modules.speech_translation_system import SpeechTranslationSystem
from src.utils.config import config


class TestSpeechTranslationSystem(unittest.TestCase):

    @patch('src.input_output.audio_device_manager.get_audio_devices')
    def test_no_input_output_devices(self, mock_get_audio_devices):
        mock_get_audio_devices.return_value = []
        with self.assertLogs('utils.logger', level='ERROR') as cm:
            SpeechTranslationSystem(
                None, None, config._input_language, config._output_language)
        self.assertIn(
            'No suitable audio devices were found for input or output', cm.output[0])

    @patch('src.input_output.audio_device_manager.get_audio_devices')
    def test_only_input_device(self, mock_get_audio_devices):
        mock_input_device = MagicMock()
        mock_input_device.is_input = True
        mock_input_device.is_output = False
        mock_get_audio_devices.return_value = [mock_input_device]
        with self.assertLogs('utils.logger', level='ERROR') as cm:
            SpeechTranslationSystem(
                mock_input_device, None, config._input_language, config._output_language)
        self.assertIn(
            'No suitable audio devices were found for input or output', cm.output[0])

    @patch('src.input_output.audio_device_manager.get_audio_devices')
    def test_only_output_device(self, mock_get_audio_devices):
        mock_output_device = MagicMock()
        mock_output_device.is_input = False
        mock_output_device.is_output = True
        mock_get_audio_devices.return_value = [mock_output_device]
        with self.assertLogs('utils.logger', level='ERROR') as cm:
            SpeechTranslationSystem(
                None, mock_output_device, config._input_language, config._output_language)
        self.assertIn(
            'No suitable audio devices were found for input or output', cm.output[0])

    @patch('src.input_output.audio_device_manager.get_audio_devices')
    @patch('src.modules.speech_translation_system.SpeechTranslationSystem.run')
    def test_input_output_devices(self, mock_run, mock_get_audio_devices):
        mock_input_device = MagicMock()
        mock_input_device.is_input = True
        mock_input_device.is_output = False
        mock_output_device = MagicMock()
        mock_output_device.is_input = False
        mock_output_device.is_output = True
        mock_get_audio_devices.return_value = [
            mock_input_device, mock_output_device]
        translation_system = SpeechTranslationSystem(
            mock_input_device, mock_output_device, config._input_language, config._output_language)
        translation_system.run()
        mock_run.assert_called_once()
