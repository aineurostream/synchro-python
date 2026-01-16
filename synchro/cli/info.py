import click


@click.group(help="System info and management")
def manager() -> None:
    """System information and management"""


@manager.command(help="""Display system information""")
def devices() -> None:
    pass
