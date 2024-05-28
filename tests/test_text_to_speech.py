import unittest
from unittest.mock import patch, MagicMock
from src.data_processing.text_to_speech import TextToSpeech


class TestTextToSpeech(unittest.TestCase):

    @patch('espeak_ng.EspeakNG')
    def test_text_to_speech(self, mock_espeak_ng):
        language = 'en'
        text = 'Hello, world!'
        expected_audio_data = b'audio_data'
        mock_espeak_ng.return_value.synth_wav.return_value = expected_audio_data

        tts = TextToSpeech(language)
        audio_data = tts.text_to_speech(text)

        mock_espeak_ng.return_value.synth_wav.assert_called_with(
            text, language=language)
        self.assertEqual(audio_data, expected_audio_data)

    @patch('espeak_ng.EspeakNG')
    def test_text_to_speech_empty_text(self, mock_espeak_ng):
        language = 'fr'
        text = ''
        expected_audio_data = b''
        mock_espeak_ng.return_value.synth_wav.return_value = expected_audio_data

        tts = TextToSpeech(language)
        audio_data = tts.text_to_speech(text)

        mock_espeak_ng.return_value.synth_wav.assert_called_with(
            text, language=language)
        self.assertEqual(audio_data, expected_audio_data)

    @patch('espeak_ng.EspeakNG')
    def test_text_to_speech_non_string_text(self, mock_espeak_ng):
        language = 'de'
        text = 42
        expected_audio_data = b'audio_data'
        mock_espeak_ng.return_value.synth_wav.return_value = expected_audio_data

        tts = TextToSpeech(language)
        with self.assertRaises(TypeError):
            tts.text_to_speech(text)

        mock_espeak_ng.return_value.synth_wav.assert_not_called()
