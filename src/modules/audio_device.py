import pyaudio
from utils.logger import log

"""
Represents an audio device with information about its input and output capabilities.

Args:
    device_index (int): The index of the audio device.
    device_info (dict): A dictionary containing information about the audio device, such as its name and the number of input and output channels.

Attributes:
    device_index (int): The index of the audio device.
    device_info (dict): A dictionary containing information about the audio device.
    is_input (bool): Indicates whether the audio device has input channels.
    is_output (bool): Indicates whether the audio device has output channels.
    name (str): The name of the audio device.
"""
class AudioDevice:
  def __init__(self, device_index, device_info):
    self.device_index = device_index
    self.device_info = device_info
    self.is_input = device_info["maxInputChannels"] > 0
    self.is_output = device_info["maxOutputChannels"] > 0
    self.name = device_info["name"]
  
  def __str__(self):
    log(f"Audio device: {self.name} (Input: {self.is_input}, Output: {self.is_output})")
    return f"Audio device: {self.name} (Input: {self.is_input}, Output: {self.is_output})"