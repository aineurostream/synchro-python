import unittest
from unittest.mock import patch, MagicMock
from src.data_processing.speech_to_text import SpeechToText


class TestSpeechToText(unittest.TestCase):

    @patch('whisper.load_model')
    def test_speech_to_text(self, mock_load_model):
        language = 'en'
        audio_data = b'audio_data'
        expected_text = 'Hello, world!'
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {'text': expected_text}
        mock_load_model.return_value = mock_model

        stt = SpeechToText(language)
        text = stt.speech_to_text(audio_data)

        mock_load_model.assert_called_once_with("base")
        mock_model.transcribe.assert_called_once_with(
            audio_data, language=language)
        self.assertEqual(text, expected_text)

    @patch('whisper.load_model')
    def test_speech_to_text_empty_audio(self, mock_load_model):
        language = 'fr'
        audio_data = b''
        expected_text = ''
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {'text': expected_text}
        mock_load_model.return_value = mock_model

        stt = SpeechToText(language)
        text = stt.speech_to_text(audio_data)

        mock_load_model.assert_called_once_with("base")
        mock_model.transcribe.assert_called_once_with(
            audio_data, language=language)
        self.assertEqual(text, expected_text)

    @patch('whisper.load_model')
    def test_speech_to_text_non_bytes_audio(self, mock_load_model):
        language = 'de'
        audio_data = 'not bytes'
        mock_load_model.return_value = MagicMock()

        stt = SpeechToText(language)
        with self.assertRaises(TypeError):
            stt.speech_to_text(audio_data)

        mock_load_model.assert_called_once_with("base")
        mock_load_model.return_value.transcribe.assert_not_called()
