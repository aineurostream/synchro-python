import unittest
from unittest.mock import patch, MagicMock
from src.data_processing.speech_translation import SpeechTranslation
from models.seamless_streaming import SeamlessStreamingModel


class TestSpeechTranslation(unittest.TestCase):

    @patch('models.seamless_streaming.SeamlessStreamingModel')
    def test_init(self, mock_model):
        source_language = 'en'
        target_language = 'fr'
        speech_translation = SpeechTranslation(
            source_language, target_language)
        self.assertEqual(speech_translation.source_language, source_language)
        self.assertEqual(speech_translation.target_language, target_language)
        mock_model.assert_called_once()

    @patch('models.seamless_streaming.SeamlessStreamingModel.translate_speech')
    def test_translate_speech(self, mock_translate_speech):
        source_language = 'en'
        target_language = 'fr'
        audio_data = b'audio_data'
        expected_translation = 'Translated text'
        mock_translate_speech.return_value = expected_translation

        speech_translation = SpeechTranslation(
            source_language, target_language)
        translation = speech_translation.translate_speech(audio_data)

        self.assertEqual(translation, expected_translation)
        mock_translate_speech.assert_called_once_with(
            audio_data, source_language, target_language)

    def test_translate_speech_invalid_audio_data(self):
        source_language = 'en'
        target_language = 'fr'
        invalid_audio_data = 'invalid_audio_data'

        speech_translation = SpeechTranslation(
            source_language, target_language)
        with self.assertRaises(TypeError):
            speech_translation.translate_speech(invalid_audio_data)
