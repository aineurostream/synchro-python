import json
import wave
from collections import defaultdict

import click

from synchro.audio.audio_device import DeviceMode
from synchro.audio.audio_device_manager import AudioDeviceManager
from synchro.cli.utils.formatting import cli_echo_title
from synchro.config.audio_format import AudioFormat, AudioFormatType
from synchro.config.commons import StreamConfig
from synchro.config.schemas import (
    BaseNodeSchema,
    InputFileStreamerNodeSchema,
    MixerNodeSchema,
    OutputChannelStreamerNodeSchema,
    OutputFileNodeSchema,
    ResamplerNodeSchema,
    SeamlessConnectorNodeSchema,
)


@click.group(help="Setup graph helpers")
def manager() -> None:
    """System information and management"""


def _node_input_creator(
    index: int,
    file_path: str,
    language: str,
    delay_ms: int,
) -> InputFileStreamerNodeSchema:
    """Create input for the node"""
    with wave.open(file_path, "rb") as wav_file:
        stream_config = StreamConfig(
            language=language,
            audio_format=AudioFormat(format_type=AudioFormatType.INT_16),
            rate=wav_file.getframerate(),
        )

    return InputFileStreamerNodeSchema(
        name=f"input_file_{index}_{language}",
        path=file_path,
        delay_ms=delay_ms,
        stream=stream_config,
        looping=True,
    )


def _node_file_output_creator(
    index: int,
    language: str,
    file_path: str,
    rate: int,
) -> OutputFileNodeSchema:
    """Create output for the node"""
    stream_config = StreamConfig(
        language=language,
        audio_format=AudioFormat(format_type=AudioFormatType.INT_16),
        rate=rate,
    )

    return OutputFileNodeSchema(
        name=f"output_file_{index}_{language}",
        path=file_path,
        stream=stream_config,
        looping=True,
    )


def _node_device_creator(
    index: int,
    language: str,
) -> OutputChannelStreamerNodeSchema:
    """Create output for the node"""
    devices = AudioDeviceManager.list_default_audio_devices()
    output_device = next(
        device
        for device in devices
        if device.mode == DeviceMode.OUTPUT or device.name == "default"
    )

    stream_config = StreamConfig(
        language=language,
        audio_format=AudioFormat(format_type=AudioFormatType.INT_16),
        rate=output_device.default_sample_rate,
    )

    return OutputChannelStreamerNodeSchema(
        name=f"output_device_{index}_{language}",
        device=output_device.index,
        stream=stream_config,
        looping=True,
    )


@manager.command(help="""Generate graph configuration from the setup""")
@click.option(
    "-s",
    "--setup",
    required=True,
    type=click.Path(exists=True),
    help="Main setup file",
)
@click.option(
    "-c",
    "--config",
    required=True,
    type=click.Path(),
    help="Configuration file output",
)
def generate(setup: str, config: str) -> None:  # noqa: C901, PLR0912, PLR0915
    """Display system information"""
    cli_echo_title("Generate graph configuration from the setup")

    with open(setup) as setup_file:
        setup_data = json.load(setup_file)

    nodes: list[BaseNodeSchema] = []
    edges: list[tuple[str, str]] = []

    language_set = {
        item["language"] for item in setup_data["inputs"] if item["language"] != "all"
    }

    desired_rate = setup_data["sample_rate"]
    desired_model = setup_data["model"]
    no_model = setup_data.get("no_model", False)

    converter_outputs: dict[str, list[str]] = defaultdict(list)

    for index, input_setup in enumerate(setup_data["inputs"]):
        language = input_setup["language"]

        input_node = _node_input_creator(
            index=index,
            file_path=input_setup["file"],
            language=language,
            delay_ms=input_setup.get("delay_ms", 0),
        )
        nodes.append(input_node)

        found_rate = input_node.stream.rate
        resampler_node = None
        if found_rate != desired_rate:
            resampler_node = ResamplerNodeSchema(
                name=f"resampler_input_{index}_{language}",
                to_rate=desired_rate,
            )
            nodes.append(resampler_node)
            edges.append((input_node.name, resampler_node.name))

        for language_other in language_set:
            if language_other == language:
                continue

            if no_model:
                if resampler_node is not None:
                    converter_outputs[language_other].append(resampler_node.name)
                else:
                    converter_outputs[language_other].append(input_node.name)
            else:
                converter_node = SeamlessConnectorNodeSchema(
                    name=f"converter_{index}_{language}_{language_other}",
                    server_url=desired_model,
                    from_language=language,
                    to_language=language_other,
                )
                nodes.append(converter_node)
                if resampler_node is not None:
                    edges.append((resampler_node.name, converter_node.name))
                else:
                    edges.append((input_node.name, converter_node.name))

                converter_outputs[language_other].append(converter_node.name)

    for index, output_setup in enumerate(setup_data["outputs"]):
        if "device" in output_setup:
            output_node = _node_device_creator(
                index=index,
                language=output_setup["language"],
            )
        elif "file" in output_setup:
            output_node = _node_file_output_creator(
                index=index,
                language=output_setup["language"],
                file_path=output_setup["file"],
                rate=desired_rate,
            )
        else:
            raise TypeError("Unknown output type")

        nodes.append(output_node)
        resampler_node = None
        if output_node.stream.rate != desired_rate:
            resampler_node = ResamplerNodeSchema(
                name=f"resampler_output_{index}",
                to_rate=output_node.stream.rate,
            )
            nodes.append(resampler_node)
            edges.append((resampler_node.name, output_node.name))

        mixer_inputs = [
            model_output
            for lang in language_set
            for model_output in converter_outputs[lang]
            if output_node.stream.language == "all" or lang == output_setup["language"]
        ]

        mixer_node = MixerNodeSchema(
            name=f"mixer_{index}_{output_setup['language']}",
        )
        nodes.append(mixer_node)

        if resampler_node is not None:
            edges.append((mixer_node.name, resampler_node.name))
        else:
            edges.append((mixer_node.name, output_node.name))

        edges += [
            (converter_node_input, mixer_node.name)
            for converter_node_input in mixer_inputs
        ]

    with open(config, "w") as config_file:
        json.dump(
            {
                "nodes": [node.model_dump(mode="json") for node in nodes],
                "edges": edges,
            },
            config_file,
            indent=4,
        )
