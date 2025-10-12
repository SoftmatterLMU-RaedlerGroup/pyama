"""Primary application window hosting all PyAMA views without MVC separation."""

from PySide6.QtWidgets import QMainWindow, QTabWidget

from pyama_qt.processing.main_tab import ProcessingPage
from pyama_qt.analysis.main_tab import AnalysisPage
from pyama_qt.visualization.main_tab import VisualizationPage


class MainWindow(QMainWindow):
    """Top-level window assembling the Processing, Analysis, and Visualization tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PyAMA-Qt")
        self.resize(1600, 640)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.North)
        tabs.setMovable(False)
        tabs.setTabsClosable(False)
        tabs.setDocumentMode(True)

        self.processing_page = ProcessingPage(self)
        self.analysis_page = AnalysisPage(self)
        self.visualization_page = VisualizationPage(self)

        # Coordinate between processing and visualization pages to prevent conflicts
        self.visualization_page.set_processing_status_model(
            self.processing_page.status_model()
        )

        tabs.addTab(self.processing_page, "Processing")
        tabs.addTab(self.analysis_page, "Analysis")
        tabs.addTab(self.visualization_page, "Visualization")

        self.setCentralWidget(tabs)