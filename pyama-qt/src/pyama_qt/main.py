#!/usr/bin/env python3
"""
Unified PyAMA-Qt application with bottom tabs for Processing, Analysis, and Visualization.
Order of tabs: Processing, Analysis, Visualization.
"""

import sys
import logging
import multiprocessing as mp
from PySide6.QtCore import QTimer
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
        self.processing_page = ProcessingPage(self)
        self.analysis_page = AnalysisPage(self)
        self.visualization_page = VisualizationPage(self)
        
        tabs.addTab(self.processing_page, "Processing")
        tabs.addTab(self.analysis_page, "Analysis")
        tabs.addTab(self.visualization_page, "Visualization")

        self.setCentralWidget(tabs)

    def closeEvent(self, event):
        """Handle application close event to clean up resources."""
        # Clean up any running threads in each page controller
        try:
            # Clean up processing controller (including microscopy loader)
            if hasattr(self.processing_page, 'controller'):
                self.processing_page.controller.cleanup()
            
            # Cancel any running analysis fitting
            if hasattr(self.analysis_page, 'controller'):
                self.analysis_page.controller.cancel_fitting()
            
            # Cancel any running visualization loading
            if hasattr(self.visualization_page, 'controller'):
                self.visualization_page.controller.cancel_loading()
            
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
        
        # Accept the close event
        event.accept()
        
        # Quit the application cleanly
        QApplication.instance().quit()


def main():
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

    window = MainApp()
    window.show()

    # Execute the application
    exit_code = app.exec()
    
    # Ensure clean shutdown
    app.processEvents()  # Process any remaining events
    app.quit()  # Explicitly quit
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
