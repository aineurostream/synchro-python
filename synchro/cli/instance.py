import click

from synchro.cli.utils.formatting import cli_echo_title
from synchro.config.schemas import ProcessingGraphConfig
from synchro.core import CoreManager


@click.group(help="Instance starting and stopping")
def manager() -> None:
    """Start/stop instances of the Synchro application"""


@manager.command(
    help="""
    Starts a new synchro instance.
    Example:
    python run.py instance start -c ./samples/example_config.yaml
""",
)
@click.option(
    "-c",
    "--config",
    required=True,
    type=click.Path(exists=True),
    help="Main configuration file",
)
def start(
    config: str,
) -> None:
    """Start an instance of the Synchro application"""
    cli_echo_title("Starting Synchro instance")

    with open(config) as config_file:
        core_config = ProcessingGraphConfig.model_validate_json(
            config_file.read(),
        )

    core = CoreManager(core_config)
    core.run()
