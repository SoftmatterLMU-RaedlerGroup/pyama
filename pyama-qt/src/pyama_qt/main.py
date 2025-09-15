#!/usr/bin/env python3
"""
Unified PyAMA-Qt application with bottom tabs for Processing, Analysis, and Visualization.
Order of tabs: Processing, Analysis, Visualization.
"""

import sys
import multiprocessing as mp
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

# Import the new embeddable pages
from pyama_qt.processing import ProcessingPage
from pyama_qt.analysis import AnalysisPage
from pyama_qt.visualization import VisualizationPage


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyAMA-Qt")
        self.resize(1280, 720)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)  # top tabs
        tabs.setMovable(False)
        tabs.setTabsClosable(False)
        tabs.setDocumentMode(True)  # native, flatter look without custom styles

        # Order: Processing, Analysis, Visualization
        tabs.addTab(ProcessingPage(self), "Processing")
        tabs.addTab(AnalysisPage(self), "Analysis")
        tabs.addTab(VisualizationPage(self), "Visualization")

        self.setCentralWidget(tabs)


def main():
    # Windows-safe multiprocessing setup
    mp.freeze_support()
    mp.set_start_method("spawn", force=True)

    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Qt")

    window = MainApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
