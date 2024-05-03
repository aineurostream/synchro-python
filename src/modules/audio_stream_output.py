import pyaudio
from utils.logger import log

"""
Outputs an audio stream to the specified audio device.

Args:
    device (pyaudio.PyAudioDevice): The audio device to output the stream to.
    data (bytes): The audio data to be played.
    chunk (int, optional): The chunk size to use for the audio stream. Defaults to 1024.
    format (int, optional): The audio format to use. Defaults to pyaudio.paInt16.
    channels (int, optional): The number of audio channels. Defaults to 1.
    rate (int, optional): The sample rate of the audio. Defaults to 44100.

Raises:
    Exception: If there is an error while opening or writing to the audio stream.
"""
def output_audio_stream(device, data, chunk=1024, format=pyaudio.paInt16, channels=1, rate=44100):
  audio = pyaudio.PyAudio()
  try:
    stream = audio.open(
      format=format,
      channels=channels,
      rate=rate,
      output=True,
      output_device_index=device.device_index
    )
    log(f"Вывод аудиопотока на {device.name}")
    #stream.write(data)
    with wave.open(input_file, "rb") as wave_file:
      data = wave_file.readframes(chunk)
      while data:
        stream.write(data)
        data = wave_file.readframes(chunk)

  except Exception as err:
    log(f"Ошибка при выводе аудиопотока в {device.name}: {err}", log_type="err")
  finally:
    stream.stop_stream()
    stream.close()
    audio.terminate()