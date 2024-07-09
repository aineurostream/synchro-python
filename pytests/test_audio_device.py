from synchro.modules.audio_device import AudioDevice, DeviceMode


def test_input_output_device():
    device_info = {
        "maxInputChannels": 2,
        "maxOutputChannels": 2,
        "name": "Test Audio Device",
    }
    device_index = 0
    audio_device = AudioDevice(device_index, device_info)
    assert audio_device.input_channels == 2
    assert audio_device.output_channels == 2
    assert audio_device.mode == DeviceMode.INPUT_OUTPUT
    assert audio_device.name == "Test Audio Device"


def test_input_only_device():
    device_info = {
        "maxInputChannels": 1,
        "maxOutputChannels": 0,
        "name": "Input Only Device",
    }
    device_index = 1
    audio_device = AudioDevice(device_index, device_info)
    assert audio_device.input_channels == 1
    assert audio_device.output_channels == 0
    assert audio_device.mode == DeviceMode.INPUT
    assert audio_device.name == "Input Only Device"


def test_output_only_device():
    device_info = {
        "maxInputChannels": 0,
        "maxOutputChannels": 2,
        "name": "Output Only Device",
    }
    device_index = 2
    audio_device = AudioDevice(device_index, device_info)
    assert audio_device.input_channels == 0
    assert audio_device.output_channels == 2
    assert audio_device.mode == DeviceMode.OUTPUT
    assert audio_device.name == "Output Only Device"


def test_no_input_output_device():
    device_info = {
        "maxInputChannels": 0,
        "maxOutputChannels": 0,
        "name": "No I/O Device",
    }
    device_index = 3
    audio_device = AudioDevice(device_index, device_info)
    assert audio_device.input_channels == 0
    assert audio_device.output_channels == 0
    assert audio_device.mode == DeviceMode.INACTIVE
    assert audio_device.name == "No I/O Device"
