import json

import click

from synchro.cli.utils.formatting import cli_echo_title
from synchro.config.schemas import ProcessingGraphConfig
from synchro.config.settings import SettingsSchema
from synchro.core import CoreManager


@click.group(help="Instance starting and stopping")
def manager() -> None:
    """Start/stop instances of the Synchro application"""


@manager.command(
    help="""
    Starts a new synchro instance.
    Example:
    python run.py instance start -p ./pipeline_config.json -n ./neuro_config.json
""",
)
@click.option(
    "-p",
    "--pipeline",
    required=True,
    type=click.Path(exists=True),
    help="Main pipeline configuration file",
)
@click.option(
    "-n",
    "--neuro",
    required=True,
    type=click.Path(exists=True),
    help="Neural networks configuration file",
)
def start(
    pipeline: str,
    neuro: str,
) -> None:
    """Start an instance of the Synchro application"""
    cli_echo_title("Starting Synchro instance")

    with (
        open(pipeline) as graph_config_file,
        open(neuro) as neuro_config_file,
    ):
        core_config = ProcessingGraphConfig.model_validate_json(
            graph_config_file.read(),
        )
        neuro_config = json.loads(neuro_config_file.read())

    core = CoreManager(core_config, neuro_config, SettingsSchema())
    core.run()
