import wave
from utils.logger import log

"""
Processes an audio stream by writing the data to a WAV file.

Args:
    data (bytes): The raw audio data to be written to the WAV file.
    format (int, optional): The audio format, e.g. wave.WAVE_FORMAT_PCM.
    channels (int, optional): The number of audio channels.
    rate (int, optional): The sample rate of the audio in Hz.

Returns:
    bytes: The original audio data.
"""
def process_audio_stream(data, format=None, channels=None, rate=None):
  log("Обработка данных аудиопотока...")

  if format and channels and rate:
    with wave.open("../audio/output.wav", "wb") as wave_file:
      wave_file.setparams((channels, format, rate, 0, 'NONE', 'not compressed'))
      wave_file.writeframes(data)
  
  return data