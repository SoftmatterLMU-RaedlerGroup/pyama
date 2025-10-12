"""Primary application window hosting the major PyAMA views."""

from PySide6.QtWidgets import QMainWindow, QTabWidget

from pyama_qt.controllers.analysis import AnalysisController
from pyama_qt.controllers.processing import ProcessingController
from pyama_qt.controllers.visualization import VisualizationController
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

        self.processing_controller = ProcessingController(self.processing_page)
        self.analysis_controller = AnalysisController(self.analysis_page)
        self.visualization_controller = VisualizationController(self.visualization_page)

        # Share processing status with visualization controller to prevent conflicts
        self.visualization_controller.set_processing_status_model(
            self.processing_controller.status_model()
        )

        tabs.addTab(self.processing_page, "Processing")
        tabs.addTab(self.analysis_page, "Analysis")
        tabs.addTab(self.visualization_page, "Visualization")

        self.setCentralWidget(tabs)
