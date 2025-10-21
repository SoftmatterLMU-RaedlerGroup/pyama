"""Main GUI application for pyama-air."""

from __future__ import annotations


def gui_app() -> None:
    """Launch the PyAMA GUI interface."""
    from pyama_air.gui.main_window import main

    main()


if __name__ == "__main__":  # pragma: no cover
    gui_app()
