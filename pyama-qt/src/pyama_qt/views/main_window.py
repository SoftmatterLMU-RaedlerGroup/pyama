"""Primary application window hosting the major PyAMA views."""

from PySide6.QtWidgets import QMainWindow, QTabWidget

from pyama_qt.views.analysis import AnalysisPage
from pyama_qt.views.processing import ProcessingPage
from pyama_qt.views.visualization import VisualizationPage


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

        tabs.addTab(self.processing_page, "Processing")
        tabs.addTab(self.analysis_page, "Analysis")
        tabs.addTab(self.visualization_page, "Visualization")

        self.setCentralWidget(tabs)
