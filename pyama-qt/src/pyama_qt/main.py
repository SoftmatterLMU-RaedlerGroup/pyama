#!/usr/bin/env python3
"""Application entry-point wiring together the PyAMA-Qt MVC layers."""

import logging
import multiprocessing as mp
import sys

from PySide6.QtWidgets import QApplication

from pyama_qt.views import MainWindow


def main() -> None:
    """Spin up the Qt event loop and show the primary application window."""
    mp.freeze_support()
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass

    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Qt")
    app.setQuitOnLastWindowClosed(True)

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    app.processEvents()
    app.quit()

    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
