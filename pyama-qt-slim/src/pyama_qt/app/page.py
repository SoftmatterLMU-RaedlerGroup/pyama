#!/usr/bin/env python3
"""
Unified PyAMA-Qt application with bottom tabs for Processing, Analysis, and Visualization.
Order of tabs: Processing, Analysis, Visualization.
"""

import sys

from PySide6.QtWidgets import QMainWindow, QTabWidget

# Import the new embeddable pages
from .analysis.page import AnalysisPage
from .processing.page import ProcessingPage
from .visualization.page import VisualizationPage


class MainApp(QMainWindow):
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


def main():
    from .layout import create_app, create_main_window

    app = create_app()
    window = create_main_window()
    window.show()

    # Execute the application
    exit_code = app.exec()

    # Ensure clean shutdown
    app.processEvents()  # Process any remaining events
    app.quit()  # Explicitly quit

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
