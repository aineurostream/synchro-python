import click

from synchro.cli.utils.formatting import cli_echo_title


@click.group(help="Setup graph helpers")
def manager() -> None:
    """System information and management"""


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
def generate(setup: str, config: str) -> None:
    """Display system information"""
    cli_echo_title(
        f"Generate graph configuration from the setup {setup} with config {config}",
    )
