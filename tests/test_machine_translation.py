import unittest
from unittest.mock import patch, MagicMock
from src.data_processing.machine_translation import MachineTranslation


class TestMachineTranslation(unittest.TestCase):

    @patch('fairseq.models.m2m_100.M2M100Model')
    def test_translate_text(self, mock_m2m100_model):
        source_language = 'en'
        target_language = 'fr'
        text = 'Hello, world!'
        expected_translation = 'Bonjour, le monde!'
        mock_model = mock_m2m100_model.return_value
        mock_model.encode.return_value = {'encoded_text': text}
        mock_model.generate.return_value = [1, 2, 3]
        mock_model.decode.return_value = expected_translation

        machine_translation = MachineTranslation(
            source_language, target_language)
        translation = machine_translation.translate_text(text)

        self.assertEqual(translation, expected_translation)
        mock_model.encode.assert_called_with(text, source_language)
        mock_model.generate.assert_called_with(
            encoded_text=text, target_lang=target_language)
        mock_model.decode.assert_called_with([1, 2, 3], target_language)

    @patch('fairseq.models.m2m_100.M2M100Model')
    def test_translate_text_empty_string(self, mock_m2m100_model):
        source_language = 'es'
        target_language = 'de'
        text = ''
        expected_translation = ''
        mock_model = mock_m2m100_model.return_value
        mock_model.encode.return_value = {'encoded_text': ''}
        mock_model.generate.return_value = []
        mock_model.decode.return_value = expected_translation

        machine_translation = MachineTranslation(
            source_language, target_language)
        translation = machine_translation.translate_text(text)

        self.assertEqual(translation, expected_translation)
        mock_model.encode.assert_called_with(text, source_language)
        mock_model.generate.assert_called_with(
            encoded_text='', target_lang=target_language)
        mock_model.decode.assert_called_with([], target_language)

    @patch('fairseq.models.m2m_100.M2M100Model')
    def test_translate_text_non_string_input(self, mock_m2m100_model):
        source_language = 'zh'
        target_language = 'ja'
        text = 42

        machine_translation = MachineTranslation(
            source_language, target_language)
        with self.assertRaises(TypeError):
            machine_translation.translate_text(text)

        mock_m2m100_model.return_value.encode.assert_not_called()
        mock_m2m100_model.return_value.generate.assert_not_called()
        mock_m2m100_model.return_value.decode.assert_not_called()
