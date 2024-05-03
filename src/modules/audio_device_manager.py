import pyaudio
from models.audio_device import AudioDevice
from utils.logger import log

"""
Returns a list of all available audio devices on the system.

This function uses the PyAudio library to enumerate all available audio devices and creates a list of `AudioDevice` objects representing each device. The `AudioDevice` objects contain information about the device, such as its index, name, and whether it supports input or output.

Returns:
    list[AudioDevice]: A list of all available audio devices.
"""
def get_audio_devices():
  audio = pyaudio.PyAudio()
  devices = []

  for i in range(audio.get_device_count()):
    device_info = audio.get_device_info_by_index(i)
    device = AudioDevice(i, device_info)
    devices.append(device)
  
  audio.terminate()
  return devices

"""
Tests an audio device by opening it for input and/or output. If the device is successfully opened, a log message is printed. If an error occurs, an error log message is printed.

Args:
    device (AudioDevice): The audio device to test.
"""
def test_audio_device(device):
  audio = pyaudio.PyAudio()
  try:
    if device.is_input:
      audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=44100,
        input=True,
        input_device_index=device.device_index
      )
    if device.is_output:
      audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=4100,
        output=True,
        output_device_index=device.device_index
      )
    log(f"Успешно открыто {device.name}")
  except Exception as err:
    log(f"Ошибка при открытие {device.name}: {err}", log_type="err")
  finally:
    audio.terminate()