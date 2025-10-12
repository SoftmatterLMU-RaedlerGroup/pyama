"""Primary application window hosting all PyAMA views without MVC separation."""

from PySide6.QtWidgets import QMainWindow, QTabWidget

from pyama_qt.processing.main_tab import ProcessingTab
from pyama_qt.analysis.main_tab import AnalysisTab
from pyama_qt.visualization.main_tab import VisualizationTab


class MainWindow(QMainWindow):
    """Top-level window assembling the Processing, Analysis, and Visualization tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PyAMA-Qt")
        self.resize(1600, 800)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.North)
        tabs.setMovable(False)
        tabs.setTabsClosable(False)
        tabs.setDocumentMode(True)

        # Instantiate the new, consolidated tab widgets
        self.processing_tab = ProcessingTab(self)
        self.analysis_tab = AnalysisTab(self)
        self.visualization_tab = VisualizationTab(self)

        # The new design removes the need for direct model/controller coupling
        # between tabs. Each tab is now self-contained.

        tabs.addTab(self.processing_tab, "Processing")
        tabs.addTab(self.analysis_tab, "Analysis")
        tabs.addTab(self.visualization_tab, "Visualization")

        self.setCentralWidget(tabs)