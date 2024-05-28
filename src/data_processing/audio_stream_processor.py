import wave
from data_processing.speech_to_text import SpeechToText
from data_processing.speech_translation import SpeechTranslation
from data_processing.machine_translation import MachineTranslation
from data_processing.text_to_speech import TextToSpeech
from threading import Thread
from utils.logger import log
from queue import Queue


"""
Class representing an audio stream processor.

The AudioStreamProcessor class is responsible for processing audio streams by performing speech-to-text, translation, and text-to-speech operations. It utilizes instances of SpeechToText, SpeechTranslation, MachineTranslation, and TextToSpeech classes for these operations.

Attributes:
    audio_capture: An object representing the audio capture device.
    source_language: The language of the input audio stream.
    target_language: The language to which the audio stream will be translated.
    stt_model: An instance of SpeechToText for performing speech-to-text conversion.
    translation_model: An instance of SpeechTranslation for translating speech.
    mt_model: An instance of MachineTranslation for translating text.
    tts_model: An instance of TextToSpeech for converting text to speech.
    processing_queue: A queue for storing audio frames to be processed.
    processing_threads: A list to store processing threads.

Methods:
    process_and_output: Starts the audio capture and output processes, processes audio frames, and outputs the processed audio.
    _process_stream: Private method to process audio frames by performing speech-to-text, translation, and text-to-speech operations.

Exceptions:
    Any exceptions that occur during the processing of audio streams are caught and logged using the 'err' log type.

Note:
    This class is designed to handle real-time audio processing and translation tasks.
"""
class AudioStreamProcessor:
    def __init__(self, audio_capture, source_language, target_language):
        self.audio_capture = audio_capture
        self.stt_model = SpeechToText(source_language)
        self.translation_model = SpeechTranslation(source_language, target_language)
        self.mt_model = MachineTranslation(source_language, target_language)
        self.tts_model = TextToSpeech(target_language)
        self.processing_queue = Queue()
        self.processing_threads = []

    def process_and_output(self, audio_output):
        self.audio_capture.start_capture()
        audio_output.start_output()

        try:
            while True:
                audio_frames = self.audio_capture.get_audio_frames()
                if not audio_frames:
                    break

                self.processing_queue.put(audio_frames)
                thread = Thread(target=self._process_stream, args=(audio_output,))
                thread.start()
                self.processing_threads.append(thread)
            
            for thread in self.processing_threads:
                thread.join()
        
        except Exception as err:
            log(f"Error during audio stream processing: {err}", log_type="err")
        
        finally:
            self.audio_capture.stop_capture()
            audio_output.stop_output()
    
    def _process_stream(self, audio_output):
        while not self.processing_queue.empty():
            audio_frames = self.processing_queue.get()
            try:
                text = self.stt_model.speech_to_text(audio_frames)
                translated_text = self.translation_model.translate_speech(text)
                audio_data = self.tts_model.text_to_speech(translated_text)
                audio_output.write_audio_frames(audio_data)
            except Exception as err:
                log(f"Error during audio stream processing: {err}", log_type="err")
