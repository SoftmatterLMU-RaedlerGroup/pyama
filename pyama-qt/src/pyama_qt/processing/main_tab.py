"""Processing tab - orchestrates workflow and merge functionality."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QHBoxLayout, QStatusBar, QWidget

from pyama_qt.processing.merge import ProcessingMergePanel
from pyama_qt.processing.workflow import ProcessingConfigPanel

logger = logging.getLogger(__name__)


# =============================================================================
# STATUS MODEL
# =============================================================================


class SimpleStatusModel(QObject):
    """Simple status model for tracking processing state."""

    isProcessingChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self._is_processing = False

    def is_processing(self) -> bool:
        return self._is_processing

    def set_is_processing(self, state: bool):
        if self._is_processing != state:
            self._is_processing = state
            self.isProcessingChanged.emit(state)


# =============================================================================
# MAIN PROCESSING TAB
# =============================================================================


class ProcessingTab(QWidget):
    """Processing page orchestrator - connects workflow and merge panels."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_model = SimpleStatusModel()
        self._setup_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _setup_ui(self) -> None:
        """Create the user interface layout."""
        self._status_bar = QStatusBar()
        layout = QHBoxLayout(self)

        self.config_panel = ProcessingConfigPanel(self)
        self.merge_panel = ProcessingMergePanel(self)

        layout.addWidget(self.config_panel, 2)
        layout.addWidget(self.merge_panel, 1)

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect panel signals to status bar and processing state."""
        # Workflow panel signals
        self.config_panel.workflow_started.connect(self._on_workflow_started)
        self.config_panel.workflow_finished.connect(self._on_workflow_finished)
        self.config_panel.status_message.connect(self._show_status)

        # Merge panel signals
        self.merge_panel.merge_started.connect(self._on_merge_started)
        self.merge_panel.merge_finished.connect(self._on_merge_finished)
        self.merge_panel.status_message.connect(self._show_status)

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    def _on_workflow_started(self) -> None:
        """Handle workflow started."""
        logger.info("Workflow started")
        self._status_model.set_is_processing(True)

    def _on_workflow_finished(self, success: bool, message: str) -> None:
        """Handle workflow finished."""
        logger.info("Workflow finished (success=%s): %s", success, message)
        self._status_model.set_is_processing(False)

    def _on_merge_started(self) -> None:
        """Handle merge started."""
        logger.info("Merge started")

    def _on_merge_finished(self, success: bool, message: str) -> None:
        """Handle merge finished."""
        logger.info("Merge finished (success=%s): %s", success, message)

    def _show_status(self, message: str) -> None:
        """Show status message in status bar."""
        self._status_bar.showMessage(message)

    # ------------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------------
    def status_bar(self) -> QStatusBar:
        """Return the status bar for external use."""
        return self._status_bar

    def is_processing(self) -> bool:
        """Return whether processing is active."""
        return self._status_model.is_processing()

    def status_model(self) -> SimpleStatusModel:
        """Return the status model for external use."""
        return self._status_model
