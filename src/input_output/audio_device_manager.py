import pyaudio
from modules.audio_device import AudioDevice
from utils.logger import log


"""
Retrieve a list of audio devices available on the system using PyAudio library.

Returns:
    list: A list of AudioDevice objects representing the available audio devices.
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
Test the audio devices by opening them for input and output.

Args:
    devices (list): A list of AudioDevice objects representing the audio devices to test.

Returns:
    None

Raises:
    Any exception raised during the process.

The function opens each device for input and/or output using PyAudio library. It logs the success or failure of opening each device using the 'log' function from the 'utils.logger' module.
"""
def test_audio_device(devices):
    audio = pyaudio.PyAudio()

    try:
        for device in devices:
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
                    rate=44100,
                    output=True,
                    output_device_index=device.device_index
                )
            log(f"Successfully opened {device.name}")
    except Exception as err:
        log(f"Opening error {device.name}: {err}", log_type="err")
    finally:
        audio.terminate()
