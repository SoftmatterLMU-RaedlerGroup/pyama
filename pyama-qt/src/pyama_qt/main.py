#!/usr/bin/env python3
"""Application entry-point wiring together the PyAMA-Qt consolidated widgets."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
import multiprocessing as mp
import sys

from PySide6.QtWidgets import QApplication

from pyama_qt.main_window import MainWindow


# =============================================================================
# MAIN APPLICATION ENTRY POINT
# =============================================================================

def main() -> None:
    """Spin up the Qt event loop and show the primary application window."""
    # ------------------------------------------------------------------------
    # MULTIPROCESSING CONFIGURATION
    # ------------------------------------------------------------------------
    mp.freeze_support()
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        # Method may already be set in some environments
        pass

    # ------------------------------------------------------------------------
    # LOGGING CONFIGURATION
    # ------------------------------------------------------------------------
    logging.basicConfig(level=logging.INFO)

    # ------------------------------------------------------------------------
    # QT APPLICATION SETUP
    # ------------------------------------------------------------------------
    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Qt")
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
