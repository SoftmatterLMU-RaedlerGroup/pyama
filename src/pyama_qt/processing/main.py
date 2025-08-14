#!/usr/bin/env python3
"""
Main entry point for the PyAMA Qt processing application.
"""

import sys
import multiprocessing as mp

from PySide6.QtWidgets import QApplication

from pyama_qt.processing.ui.main_window import MainWindow


def main():
    """Initialize and run the Qt application."""
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    mp.freeze_support()
    mp.set_start_method("spawn", True)
    main()
