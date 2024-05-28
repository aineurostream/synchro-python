import pyaudio
import wave
from utils.logger import log


"""
Class representing an audio stream capture object.

Attributes:
    device (object): The audio input device to capture audio from.
    chunk (int): The number of frames per buffer to read from the audio stream.
    format (int): The audio format to use for capturing (default is pyaudio.paInt16).
    channels (int): The number of audio channels (default is 1).
    rate (int): The sampling rate in Hz (default is 44100).
    audio (pyaudio.PyAudio): The PyAudio instance for audio operations.
    stream (pyaudio.Stream): The audio stream object for capturing audio.

Methods:
    start_capture(): Opens the audio stream for capturing audio.
    get_audio_frames(): Reads and returns audio frames from the stream.
    stop_capture(): Stops and closes the audio stream.
"""
class AudioStreamCapture:
    def __init__(self, device, chunk=1024, format=pyaudio.paInt16, channels=1, rate=44100):
        self.device = device
        self.chunk = chunk
        self.format = format
        self.channels = channels
        self.rate = rate
        self.audio = pyaudio.PyAudio()
        self.stream = None
    
    def start_capture(self):
        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.device.device_index,
                frames_per_buffer=self.chunk
            )
            log(f"Capture audio stream from {self.device.name}")
        except Exception as err:
            log(f"Error when capturing an audio stream from the {self.device.name}: {err}", log_type="err")
    
    def get_audio_frames(self):
        if self.stream:
            return self.stream.read(self.chunk)
        return None
    
    def stop_capture(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
