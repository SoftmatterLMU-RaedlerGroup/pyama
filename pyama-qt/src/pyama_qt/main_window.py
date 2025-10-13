"""Primary application window hosting all PyAMA views without MVC separation."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtWidgets import QMainWindow, QTabWidget

from pyama_qt.processing.main_tab import ProcessingTab
from pyama_qt.analysis.main_tab import AnalysisTab
from pyama_qt.visualization.main_tab import VisualizationTab

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN WINDOW CLASS
# =============================================================================

class MainWindow(QMainWindow):
    """Top-level window assembling the Processing, Analysis, and Visualization tabs."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self) -> None:
        super().__init__()
        self._setup_window()
        self._create_tabs()
        self._connect_tabs()
        self._finalize_window()

    # ------------------------------------------------------------------------
    # WINDOW SETUP
    # ------------------------------------------------------------------------
    def _setup_window(self) -> None:
        """Configure basic window properties."""
        self.setWindowTitle("PyAMA-Qt")
        self.resize(1600, 800)

    # ------------------------------------------------------------------------
    # TAB CREATION
    # ------------------------------------------------------------------------
    def _create_tabs(self) -> None:
        """Create the tab widget and individual tabs."""
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(False)
        self.tabs.setTabsClosable(False)
        self.tabs.setDocumentMode(True)

        # Instantiate the new, consolidated tab widgets
        self.processing_tab = ProcessingTab(self)
        self.analysis_tab = AnalysisTab(self)
        self.visualization_tab = VisualizationTab(self)

    # ------------------------------------------------------------------------
    # TAB CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_tabs(self) -> None:
        """Establish communication between tabs."""
        # The new design removes the need for direct model/controller coupling
        # between tabs. Each tab is now self-contained.

        # Connect processing status to visualization tab
        status_model = self.processing_tab.status_model()
        self.visualization_tab.set_status_model(status_model)
        
        # Connect tab change signal for debugging
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change events."""
        tab_name = self.tabs.tabText(index)
        logger.debug("UI Event: Tab changed to - %s (index %d)", tab_name, index)

    # ------------------------------------------------------------------------
    # WINDOW FINALIZATION
    # ------------------------------------------------------------------------
    def _finalize_window(self) -> None:
        """Add tabs to window and complete setup."""
        self.tabs.addTab(self.processing_tab, "Processing")
        self.tabs.addTab(self.analysis_tab, "Analysis")
        self.tabs.addTab(self.visualization_tab, "Visualization")

        self.setCentralWidget(self.tabs)