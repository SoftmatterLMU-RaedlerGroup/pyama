"""Processing tab - orchestrates workflow and merge functionality."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

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
        self._status_manager = None
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI BUILDING
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create the user interface layout."""
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
        self.config_panel.microscopy_loading_started.connect(self._on_microscopy_loading_started)
        self.config_panel.microscopy_loading_finished.connect(self._on_microscopy_loading_finished)
        
        # Connect workflow status messages directly to main window status manager
        # This will be set when the status manager is available
        self._status_connection = None

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
        if self._status_manager:
            self._status_manager.show_message("Processing workflow started...")

    def _on_workflow_finished(self, success: bool, message: str) -> None:
        """Handle workflow finished."""
        logger.info("Workflow finished (success=%s): %s", success, message)
        self._status_model.set_is_processing(False)
        if self._status_manager:
            if success:
                self._status_manager.show_message("Processing workflow completed")
            else:
                self._status_manager.show_message(f"Processing failed: {message}")

    def _on_merge_started(self) -> None:
        """Handle merge started."""
        logger.info("Merge started")
        if self._status_manager:
            self._status_manager.show_message("Merging processing results...")

    def _on_merge_finished(self, success: bool, message: str) -> None:
        """Handle merge finished."""
        logger.info("Merge finished (success=%s): %s", success, message)
        if self._status_manager:
            if success:
                self._status_manager.show_message("Merge completed")
            else:
                self._status_manager.show_message(f"Merge failed: {message}")

    def _on_microscopy_loading_started(self) -> None:
        """Handle microscopy loading started."""
        logger.info("Microscopy loading started")
        if self._status_manager:
            self._status_manager.show_message("Loading ND2 file...")

    def _on_microscopy_loading_finished(self, success: bool, message: str) -> None:
        """Handle microscopy loading finished."""
        logger.info("Microscopy loading finished (success=%s): %s", success, message)
        if self._status_manager:
            if success:
                self._status_manager.show_message("ND2 file loaded")
            else:
                self._status_manager.show_message(f"Failed to load ND2: {message}")

    def _show_status(self, message: str) -> None:
        """Show status message in main window status bar."""
        if self._status_manager:
            self._status_manager.show_message(message)

    # ------------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------------
    def is_processing(self) -> bool:
        """Return whether processing is active."""
        return self._status_model.is_processing()

    def status_model(self) -> SimpleStatusModel:
        """Return the status model for external use."""
        return self._status_model
        
    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for coordinating background operations."""
        self._status_manager = status_manager
        # Connect workflow panel status messages to main window status manager
        if self._status_connection:
            self.config_panel.status_message.disconnect(self._status_connection)
        self._status_connection = self.config_panel.status_message.connect(
            self._status_manager.show_message
        )
