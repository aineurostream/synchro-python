from modules.audio_device_manager import get_audio_devices, test_audio_device
from modules.audio_stream_capture import capture_audio_stream
from modules.audio_stream_output import output_audio_stream
from modules.audio_stream_processor import process_audio_stream
from utils.logger import log


"""
This code block is the main entry point of the application. It performs the following tasks:

1. Retrieves a list of available audio devices on the system.
2. Logs the list of audio devices to the console.
3. Tests each audio device to ensure they are functioning properly.
4. Finds the first available input audio device and captures an audio stream from it, saving it to a file named "captured_audio.wav".
5. Finds the first available output audio device and plays the captured audio stream through it.
"""
if __name__ == "__main__":
  devices = get_audio_devices()
  log("Отображение списка аудио-устройств:")
  for device in devices:
    log(device)
  
  log("Тестирование аудио-устройств:")
  for device in devices:
    test_audio_device(device)
  
  input_device = next((device for device in devices if device.is_input), None)
  if input_device:
    capture_audio_stream(input_device, output_file="captured_audio.wav", duration=10)
  
  output_device = next((device for device in devices if device.is_output), None)
  if output_device:
    output_audio_stream(output_device, input_file="captured_audio.wav")
    #data = b'....'
    #processed_data = process_audio_stream(data)
    #output_audio_stream(output_device, processed_data)
