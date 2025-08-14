#!/usr/bin/env python3
"""
PyAMA-Qt Visualization Application

Interactive visualization and analysis of microscopy processing results.
"""

import sys
from PySide6.QtWidgets import QApplication
from pyama_qt.visualization.ui.main_window import VisualizationMainWindow
import multiprocessing as mp

def main():
    """Launch the visualization application."""
    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Qt Visualizer")
    app.setApplicationVersion("0.1.0")

    window = VisualizationMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    mp.freeze_support()
    mp.set_start_method("spawn", True)
    main()
