from input_output.audio_stream_capture import AudioStreamCapture
from input_output.audio_stream_output import AudioStreamOutput
from data_processing.audio_stream_processor import AudioStreamProcessor
from threading import Thread


"""
Class representing a Speech Translation System.

The SpeechTranslationSystem class manages the flow of audio data from input devices to output devices, processing it for speech-to-text, translation, and text-to-speech functionalities. It initializes with input and output devices, as well as source and target languages for translation.

Attributes:
    input_devices (list): A list of input devices for audio capture.
    output_devices (list): A list of output devices for audio playback.
    source_language (str): The language of the input audio.
    target_language (str): The language to translate the input audio.
    audio_captures (list): A list of AudioStreamCapture instances for capturing audio.
    audio_outputs (list): A list of AudioStreamOutput instances for audio output.
    audio_processors (list): A list of AudioStreamProcessor instances for processing audio data.

Methods:
    run(): Initiates the audio capture, output, and processing threads for the system to function.

Usage:
    system = SpeechTranslationSystem(input_device, output_device, source_language, target_language)
    system.run()
"""
class SpeechTranslationSystem:
    def __init__(self, input_device, output_device, source_language, target_language):
        self.audio_captures = [AudioStreamCapture(
            device) for device in input_devices]
        self.audio_outputs = [AudioStreamOutput(
            device) for device in output_devices]
        self.audio_processors = [AudioStreamProcessor(
            capture, source_language, target_language) for capture in self.audio_captures]

    def run(self):
        threads = []
        for capture, output, processor in zip(self.audio_captures, self.audio_outputs, self.audio_processors):
            capture.start_capture()
            output.start_output()
            thread = Thread(
                target=processor.process_and_output, args=(output,))
            thread.start()
            threads.append(thread)

        try:
            for thread in threads:
                thread.join()
        finally:
            for capture in self.audio_captures:
                capture.stop_capture()
            for output in self.audio_outputs:
                output.stop_output()
