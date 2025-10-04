"""Main application layout and window management."""

import sys
import logging
import multiprocessing as mp

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from .app.analysis.page import AnalysisPage
from .app.processing.page import ProcessingPage
from .app.visualization.page import VisualizationPage


class MainApp(QMainWindow):
    """Main application window with tabbed interface."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyAMA-Qt")
        self.resize(1600, 640)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.North)  # top tabs
        tabs.setMovable(False)
        tabs.setTabsClosable(False)
        tabs.setDocumentMode(True)  # native, flatter look without custom styles

        # Order: Processing, Analysis, Visualization
        self.processing_page = ProcessingPage(self)
        self.analysis_page = AnalysisPage(self)
        self.visualization_page = VisualizationPage(self)

        tabs.addTab(self.processing_page, "Processing")
        tabs.addTab(self.analysis_page, "Analysis")
        tabs.addTab(self.visualization_page, "Visualization")

        self.setCentralWidget(tabs)


def create_app() -> QApplication:
    """Create and configure the main QApplication."""
    # Windows-safe multiprocessing setup
    mp.freeze_support()
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        # Already set, ignore
        pass

    # Simple test logging setup at top level
    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)
    app.setApplicationName("PyAMA-Qt")
    app.setQuitOnLastWindowClosed(True)

    return app


def create_main_window() -> MainApp:
    """Create and return the main application window."""
    return MainApp()
