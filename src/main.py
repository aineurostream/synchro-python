from input_output.audio_device_manager import get_audio_devices, test_audio_device
from input_output.audio_stream_capture import AudioStreamCapture
from input_output.audio_stream_output import AudioStreamOutput
from data_processing.audio_stream_processor import AudioStreamProcessor
from data_processing.speech_to_text import SpeechToText
from data_processing.machine_translation import MachineTranslation
from data_processing.text_to_speech import TextToSpeech
from modules.speech_translation_system import SpeechTranslationSystem
from utils.logger import log
from utils.config import config


if __name__ == "__main__":
    log('List of available audio devices:')
    devices = get_audio_devices()
    for device in devices:
        log(str(device))

    log('Testing audio devices:')
    test_audio_device(devices)

    input_devices = [device for device in devices if device.is_input]
    output_devices = [device for device in devices if device.is_output]

    if input_devices and output_devices:
        translation_system = SpeechTranslationSystem(
            input_device,
            output_device,
            config._input_language,
            config._output_language
        )
        translation_system.run()
    else:
        log("No suitable audio devices were found for input or output", log_type="err")
