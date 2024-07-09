import click

from synchro.cli.utils.formatting import cli_echo_title
from synchro.commons.types import ChannelLocaleRaw


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
def start(
    inputs: list[ChannelLocaleRaw],
    outputs: list[ChannelLocaleRaw],
) -> None:
    """Start an instance of the Synchro application"""
    cli_echo_title("Starting Synchro instance")
    click.echo(f"Inputs:\n{inputs}")
    click.echo(f"Outputs:\n{outputs}")
