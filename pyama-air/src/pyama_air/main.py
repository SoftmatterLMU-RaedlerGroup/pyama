#!/usr/bin/env python3
"""Application entry-point for PyAMA-Air GUI."""

# =============================================================================
# IMPORTS
# =============================================================================

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication

from pyama_air.main_window import MainWindow


# =============================================================================
# MAIN APPLICATION ENTRY POINT
# =============================================================================


def main() -> None:
    """Spin up the Qt event loop and show the primary application window."""
    # ------------------------------------------------------------------------
    # COMMAND LINE ARGUMENTS
    # ------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="PyAMA-Air streamlined GUI for processing, merging, and analysis"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # ------------------------------------------------------------------------
    # LOGGING CONFIGURATION
    # ------------------------------------------------------------------------
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    # Suppress verbose debug messages from fsspec (used by bioio)
    logging.getLogger("fsspec.local").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(
        "Starting PyAMA-Air (level=%s, debug=%s)",
        logging.getLevelName(log_level),
        args.debug,
    )

    # ------------------------------------------------------------------------
    # QT APPLICATION SETUP
    # ------------------------------------------------------------------------
    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Air")
    app.setQuitOnLastWindowClosed(True)

    # ------------------------------------------------------------------------
    # MAIN WINDOW CREATION AND DISPLAY
    # ------------------------------------------------------------------------
    window = MainWindow()
    window.show()

    # ------------------------------------------------------------------------
    # EVENT LOOP EXECUTION
    # ------------------------------------------------------------------------
    exit_code = app.exec()

    # Clean up
    app.processEvents()
    app.quit()

    sys.exit(exit_code)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
