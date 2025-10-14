"""Primary application window hosting all PyAMA views without MVC separation."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMainWindow, QTabWidget, QStatusBar, QLabel

from pyama_qt.processing.main_tab import ProcessingTab
from pyama_qt.analysis.main_tab import AnalysisTab
from pyama_qt.visualization.main_tab import VisualizationTab

logger = logging.getLogger(__name__)


# =============================================================================
# SIMPLE STATUS MANAGER
# =============================================================================


class SimpleStatusManager(QObject):
    """Simple status manager for showing user-friendly messages."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    status_message = Signal(str)  # message
    status_cleared = Signal()  # Clear the status

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    # ------------------------------------------------------------------------
    # STATUS METHODS
    # ------------------------------------------------------------------------
    def show_message(self, message: str) -> None:
        """Show a status message."""
        logger.debug("Status Bar: Showing message - %s", message)
        self.status_message.emit(message)

    def clear_status(self) -> None:
        """Clear the status message."""
        logger.debug("Status Bar: Clearing status")
        self.status_cleared.emit()


# =============================================================================
# SIMPLE STATUS BAR
# =============================================================================


class SimpleStatusBar(QStatusBar):
    """Simple status bar for displaying status messages only."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _setup_ui(self) -> None:
        """Set up the status bar UI components."""
        # Main status label
        self.status_label = QLabel("Ready")
        self.addWidget(self.status_label)

    # ------------------------------------------------------------------------
    # STATUS UPDATES
    # ------------------------------------------------------------------------
    def show_status_message(self, message: str) -> None:
        """Display status message."""
        self.status_label.setText(message)
        logger.debug("Status Bar UI: Showing - %s", message)

    def clear_status(self) -> None:
        """Clear status and show ready state."""
        self.status_label.setText("Ready")
        logger.debug("Status Bar UI: Cleared status")


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
        self.status_manager = SimpleStatusManager()
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI BUILDING
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build all UI components for the main window."""
        self._setup_window()
        self._create_status_bar()
        self._create_tabs()
        self._finalize_window()

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals and establish communication between components."""
        self._connect_tabs()

    # ------------------------------------------------------------------------
    # WINDOW SETUP
    # ------------------------------------------------------------------------
    def _setup_window(self) -> None:
        """Configure basic window properties."""
        self.setWindowTitle("PyAMA-Qt")
        self.resize(1600, 800)

    # ------------------------------------------------------------------------
    # STATUS BAR SETUP
    # ------------------------------------------------------------------------
    def _create_status_bar(self) -> None:
        """Create and configure the status bar."""
        self.status_bar = SimpleStatusBar(self)
        self.setStatusBar(self.status_bar)

        # Connect status manager signals to status bar
        self.status_manager.status_message.connect(self._on_status_message)
        self.status_manager.status_cleared.connect(self._on_status_cleared)

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

        # Connect status manager to tabs for simple message display
        self.processing_tab.set_status_manager(self.status_manager)
        self.analysis_tab.set_status_manager(self.status_manager)
        self.visualization_tab.set_status_manager(self.status_manager)

        # Connect tab change signal for debugging
        self.tabs.currentChanged.connect(self._on_tab_changed)

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

    @Slot()
    def _on_status_message(self, message: str) -> None:
        """Handle status message display."""
        self.status_bar.show_status_message(message)

    @Slot()
    def _on_status_cleared(self) -> None:
        """Handle status clearing."""
        self.status_bar.clear_status()

    @Slot(int)
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
