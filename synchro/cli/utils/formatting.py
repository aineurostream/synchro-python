import click


def cli_echo_title(title: str) -> None:
    """
    Echo a title to the CLI
    """
    click.secho(
        f" *** {title} *** ",
        bg="bright_white",
        fg="black",
        bold=True,
    )
