"""
Entry point for the PyAMA-Qt Analysis application.

Provides trace fitting analysis with parallel processing for microscopy data.
"""

import sys
import multiprocessing as mp
from PySide6.QtWidgets import QApplication

from pyama_qt.analysis.ui.main_window import MainWindow
from pyama_qt.utils.logging_config import setup_logging, get_logger


def main():
    """Main entry point for the analysis application."""
    # Required for multiprocessing on Windows
    mp.freeze_support()
    mp.set_start_method("spawn", force=True)

    # Set up logging
    setup_logging()
    logger = get_logger(__name__)

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Qt Analysis")
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
        logger.info("Starting PyAMA-Qt Analysis application")

        # Create and show main window
        window = MainWindow()
        window.show()

        # Run application
        exit_code = app.exec()

        logger.info(f"Application exiting with code {exit_code}")
        sys.exit(exit_code)

    except Exception:
        logger.exception("Critical error in analysis application")
        sys.exit(1)


if __name__ == "__main__":
    main()
