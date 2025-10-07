#!/usr/bin/env python3
"""Application entry-point wiring together the PyAMA-Qt MVC layers."""

import logging
import multiprocessing as mp
import sys

from PySide6.QtWidgets import QApplication

from pyama_qt.controllers.analysis import AnalysisController
from pyama_qt.controllers.processing import ProcessingController
from pyama_qt.controllers.visualization import VisualizationController
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

    analysis_controller = AnalysisController(window.analysis_page)
    processing_controller = ProcessingController(window.processing_page)
    visualization_controller = VisualizationController(window.visualization_page)

    # Retain controller references on the window to keep them alive
    window.analysis_controller = analysis_controller
    window.processing_controller = processing_controller
    window.visualization_controller = visualization_controller
    window.show()

    exit_code = app.exec()
    app.processEvents()
    app.quit()

    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
