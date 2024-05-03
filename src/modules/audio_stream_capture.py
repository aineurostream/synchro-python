import pyaudio
import wave
import time #
from modules.audio_stream_processor import process_audio_stream
from utils.logger import log

"""
Captures an audio stream from the specified audio device and saves it to a WAV file.

Args:
    device (pyaudio.PyAudioDevice): The audio device to capture the stream from.
    output_file (str, optional): The path to the output WAV file. Defaults to "output.wav".
    duration (int, optional): The duration of the audio capture in seconds. Defaults to 10.
    chunk (int, optional): The number of frames to read from the stream at a time. Defaults to 1024.
    format (pyaudio.paFormat, optional): The audio format to use for the capture. Defaults to pyaudio.paInt16.
    channels (int, optional): The number of audio channels to capture. Defaults to 1.
    rate (int, optional): The sample rate of the audio capture. Defaults to 44100.
    frames_per_buffer (int, optional): The number of frames to use for the buffer. Defaults to None.
"""
def capture_audio_stream(device, output_file="output.wav", duration=10, chunk=1024, format=pyaudio.paInt16, channels=1, rate=44100, frames_per_buffer=None):
  audio = pyaudio.PyAudio()
  try:
    stream = audio.open(
      format=format,
      channels=channels,
      rate=rate,
      input=True,
      input_device_index=device.device_index,
      frames_per_buffer=frames_per_buffer
    )
    log(f"Захват аудиопотока из {device.name}")

    frames = []
    start_time = time.time() #
    while time.time() - start_time < duration:
      data = stream.read(chunk)
      frames.append(data)
    #while True:
    #  data = stream.read(chunk)
      #processed_data = process_audio_stream(data, format, channels, rate)
    #  frames.append(data)
  
  except Exception as err:
    log(f"Ошибка при захвате аудиопотока из {device.name}: {err}", log_type="err")
  finally:
    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(output_file, "wb") as wave_file:
      wave_file.setnchannels(channels)
      wave_file.setsampwidth(audio.get_sample_size(format))
      wave_file.setframerate(rate)
      wave_file.writeframes(b''.join(frames))

    log(f"Аудиопоток с {device.name} сохраняется в {output_file}")