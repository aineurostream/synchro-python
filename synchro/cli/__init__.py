import click

from synchro.cli.info import manager as info_manager
from synchro.cli.instance import manager as instance_manager
from synchro.cli.setup.setup import manager as setup_manager


@click.group()
def manager() -> None:
    """
    Primary CLI for instance management - entry point
    """


manager.add_command(instance_manager, "instance")
manager.add_command(info_manager, "info")
manager.add_command(setup_manager, "setup")
