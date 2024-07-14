from typing import TypedDict, Unpack

import click

from synchro.cli.utils.formatting import cli_echo_title
from synchro.commons.types import ChannelLocale, ChannelLocaleRaw
from synchro.core import CoreManager


class ConfigDict(TypedDict):
    format: str
    rate: int
    chunk_size: int


@click.group(help="Instance starting and stopping")
def manager() -> None:
    """Start/stop instances of the Synchro application"""


@manager.command(
    help="""
Starts a new synchro instance.
Example:
python run.py instance start -i 0 0 ru -i 0 1 en -o 1 0 en -o 1 1 ru
""",
)
@click.option(
    "-i",
    "--inputs",
    default=[(0, 0, "en")],
    required=True,
    show_default=True,
    multiple=True,
    type=click.Tuple([int, int, str]),
    help="Input channels and languages in format <device_id> <channel_id> <language>",
)
@click.option(
    "-o",
    "--outputs",
    default=[(1, 0, "ru"), (1, 1, "ru")],
    required=True,
    show_default=True,
    multiple=True,
    type=click.Tuple([int, int, str]),
    help="Output channels and languages in format <device_id> <channel_id> <language>",
)
@click.option(
    "-f",
    "--format",
    default="Int16",
    required=False,
    show_default=True,
    type=str,
    help="Audio format",
)
@click.option(
    "-r",
    "--rate",
    default=44100,
    required=False,
    show_default=True,
    type=int,
    help="Audio rate",
)
@click.option(
    "-c",
    "--chunk-size",
    default=1024,
    required=False,
    show_default=True,
    type=int,
    help="Output chunk size",
)
def start(
    inputs: list[ChannelLocaleRaw],
    outputs: list[ChannelLocaleRaw],
    **config: Unpack[ConfigDict],
) -> None:
    """Start an instance of the Synchro application"""
    cli_echo_title("Starting Synchro instance")

    core = CoreManager(
        audio_format=config["format"],
        rate=config["rate"],
        chunk_size=config["chunk_size"],
    )

    for channel_input in inputs:
        core.create_input_stream(ChannelLocale.from_raw(channel_input))

    for channel_output in outputs:
        core.create_output_stream(ChannelLocale.from_raw(channel_output))

    core.run()
