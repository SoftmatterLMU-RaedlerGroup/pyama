"""Main entry point for pyama-air application."""

from __future__ import annotations

import typer

from pyama_air.cli.main import cli_app
from pyama_air.gui.main import gui_app

app = typer.Typer(
    add_completion=False,
    help="PyAMA interactive helpers with CLI and GUI interfaces.",
)


@app.command()
def cli() -> None:
    """Launch the PyAMA CLI interface."""
    cli_app()


@app.command()
def gui() -> None:
    """Launch the PyAMA GUI interface."""
    gui_app()


if __name__ == "__main__":  # pragma: no cover
    app()
