import click

from synchro.cli.utils.formatting import cli_echo_title
from synchro.input_output.audio_device_manager import AudioDeviceManager


@click.group(help="System info and management")
def manager() -> None:
    """System information and management"""


@manager.command(help="""Display system information""")
def devices() -> None:
    """Display system information"""
    cli_echo_title("List of default audio devices")
    all_devices = AudioDeviceManager.list_default_audio_devices()
    for device in all_devices:
        click.echo(f"   - {device}")

    cli_echo_title("List of available audio devices")
    all_devices = AudioDeviceManager.list_audio_devices()
    for device in all_devices:
        click.echo(f"   - {device}")
