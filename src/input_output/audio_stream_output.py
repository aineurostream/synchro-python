import pyaudio
from utils.logger import log


"""
Class representing an audio stream output handler.

Attributes:
    device (object): The audio output device.
    chunk (int): The number of frames in a buffer.
    format (int): The format of the audio data.
    channels (int): The number of audio channels.
    rate (int): The sampling rate of the audio.
    audio (pyaudio.PyAudio): The PyAudio instance for audio operations.
    stream (pyaudio.Stream): The audio stream for output.

Methods:
    start_output(): Opens the audio stream for output.
    write_audio_frames(frames): Writes audio frames to the output stream.
    stop_output(): Stops and closes the audio output stream.

Usage:
    audio_output = AudioStreamOutput(device, chunk, format, channels, rate)
    audio_output.start_output()
    audio_output.write_audio_frames(frames)
    audio_output.stop_output()
"""
class AudioStreamOutput:
    def __init__(self, device, chunk=1024, format=pyaudio.paInt16, channels=1, rate=44100):
        self.device = device
        self.chunk = chunk
        self.format = format
        self.channels = channels
        self.rate = rate
        self.audio = pyaudio.PyAudio()
        self.stream = None
    
    def start_output(self):
        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                output=True,
                output_device_index=self.device.device_index
            )
            log(f"Output audio stream from {self.device.name}")
        except Exception as err:
            log(f"Error when outputting an audio stream to the {self.device.name}: {err}", log_type="err")

    def write_audio_frames(self, frames):
        if self.stream:
            self.stream.write(frames)
    
    def stop_output(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
