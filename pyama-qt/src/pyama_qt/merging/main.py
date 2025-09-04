#!/usr/bin/env python3
"""
Main entry point for the PyAMA Qt merge application.

This application provides a GUI interface for merging processing results
from multiple fields of view (FOVs) into sample-level CSV files suitable
for analysis. It bridges the processing and analysis modules in the
PyAMA microscopy analysis pipeline.
"""

import sys
import multiprocessing as mp
from PySide6.QtWidgets import QApplication

from pyama_qt.merge.ui.main_window import MainWindow
import logging


def main():
    """Main entry point for the merge application."""
    # Required for multiprocessing on Windows
    mp.freeze_support()
    mp.set_start_method("spawn", force=True)

    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Qt Merge")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PyAMA Team")

    # Set application icon if available
    try:
        pass
        # Try to set an icon - this would be the path to your app icon
        # app.setWindowIcon(QIcon("path/to/icon.png"))
    except Exception:
        pass

    try:
        logger.info("Starting PyAMA-Qt Merge application")

        # Create and show main window
        window = MainWindow()
        window.show()

        # Run application
        exit_code = app.exec()

        logger.info(f"Application exiting with code {exit_code}")
        sys.exit(exit_code)

    except Exception:
        logger.exception("Critical error in merge application")
        sys.exit(1)


if __name__ == "__main__":
    main()