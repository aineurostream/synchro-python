import unittest
from unittest.mock import MagicMock, patch
from src.data_processing.audio_stream_processor import AudioStreamProcessor
from src.data_processing.speech_to_text import SpeechToText
from src.data_processing.speech_translation import SpeechTranslation
from src.data_processing.machine_translation import MachineTranslation
from src.data_processing.text_to_speech import TextToSpeech


class TestAudioStreamProcessor(unittest.TestCase):

    @patch('src.data_processing.audio_stream_processor.SpeechToText')
    @patch('src.data_processing.audio_stream_processor.SpeechTranslation')
    @patch('src.data_processing.audio_stream_processor.MachineTranslation')
    @patch('src.data_processing.audio_stream_processor.TextToSpeech')
    def test_init(self, mock_tts, mock_mt, mock_translation, mock_stt):
        audio_capture = MagicMock()
        source_language = 'en'
        target_language = 'fr'
        processor = AudioStreamProcessor(
            audio_capture, source_language, target_language)

        self.assertEqual(processor.audio_capture, audio_capture)
        mock_stt.assert_called_once_with(source_language)
        mock_translation.assert_called_once_with(
            source_language, target_language)
        mock_mt.assert_called_once_with(source_language, target_language)
        mock_tts.assert_called_once_with(target_language)

    @patch('src.data_processing.audio_stream_processor.Thread')
    @patch('src.data_processing.audio_stream_processor.SpeechToText')
    @patch('src.data_processing.audio_stream_processor.SpeechTranslation')
    @patch('src.data_processing.audio_stream_processor.MachineTranslation')
    @patch('src.data_processing.audio_stream_processor.TextToSpeech')
    def test_process_and_output(self, mock_tts, mock_mt, mock_translation, mock_stt, mock_thread):
        audio_capture = MagicMock()
        audio_output = MagicMock()
        source_language = 'en'
        target_language = 'fr'
        processor = AudioStreamProcessor(
            audio_capture, source_language, target_language)

        processor.process_and_output(audio_output)

        audio_capture.start_capture.assert_called_once()
        audio_output.start_output.assert_called_once()
        audio_capture.stop_capture.assert_called_once()
        audio_output.stop_output.assert_called_once()

    @patch('src.data_processing.audio_stream_processor.SpeechToText')
    @patch('src.data_processing.audio_stream_processor.SpeechTranslation')
    @patch('src.data_processing.audio_stream_processor.MachineTranslation')
    @patch('src.data_processing.audio_stream_processor.TextToSpeech')
    def test_process_stream(self, mock_tts, mock_mt, mock_translation, mock_stt):
        audio_capture = MagicMock()
        audio_output = MagicMock()
        source_language = 'en'
        target_language = 'fr'
        processor = AudioStreamProcessor(
            audio_capture, source_language, target_language)

        mock_stt.return_value.speech_to_text.return_value = 'Hello'
        mock_translation.return_value.translate_speech.return_value = 'Bonjour'
        mock_tts.return_value.text_to_speech.return_value = b'audio_data'

        audio_frames = b'audio_frames'
        processor.processing_queue.put(audio_frames)
        processor._process_stream(audio_output)

        mock_stt.return_value.speech_to_text.assert_called_once_with(
            audio_frames)
        mock_translation.return_value.translate_speech.assert_called_once_with(
            'Hello')
        mock_tts.return_value.text_to_speech.assert_called_once_with('Bonjour')
        audio_output.write_audio_frames.assert_called_once_with(b'audio_data')
