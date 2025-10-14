"""Processing tab - orchestrates workflow and merge functionality."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_qt.processing.merge import ProcessingMergePanel
from pyama_qt.processing.workflow import ProcessingConfigPanel

logger = logging.getLogger(__name__)


# =============================================================================
# STATUS MODEL
# =============================================================================


# =============================================================================
# MAIN PROCESSING TAB
# =============================================================================


class ProcessingTab(QWidget):
    """Processing page orchestrator - connects workflow and merge panels."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    processing_started = Signal()  # When processing starts
    processing_finished = Signal()  # When processing finishes

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_manager = None
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI BUILDING
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create the user interface layout."""
        layout = QHBoxLayout(self)

        self._config_panel = ProcessingConfigPanel(self)
        self._merge_panel = ProcessingMergePanel(self)

        layout.addWidget(self._config_panel, 2)
        layout.addWidget(self._merge_panel, 1)

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals between panels and status messages."""
        self._connect_panel_signals()
        self._connect_status_messages()

    def _connect_panel_signals(self) -> None:
        """Connect panel signals to status bar and processing state."""
        # Workflow panel signals
        self._config_panel.workflow_started.connect(self._on_workflow_started)
        self._config_panel.workflow_finished.connect(self._on_workflow_finished)
        self._config_panel.microscopy_loading_started.connect(
            self._on_microscopy_loading_started
        )
        self._config_panel.microscopy_loading_finished.connect(
            self._on_microscopy_loading_finished
        )

        # Connect workflow status messages directly to main window status manager
        # This will be set when the status manager is available
        self._status_connection = None

        # Merge panel signals
        self._merge_panel.merge_started.connect(self._on_merge_started)
        self._merge_panel.merge_finished.connect(self._on_merge_finished)
        
    def _connect_status_messages(self) -> None:
        """Connect status message signals from all panels."""
        self._merge_panel.status_message.connect(self._on_status_message)
        self._config_panel.status_message.connect(self._on_status_message)

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot()
    def _on_workflow_started(self) -> None:
        """Handle workflow started."""
        logger.info("Workflow started")
        self.processing_started.emit()
        if self._status_manager:
            self._status_manager.show_message("Processing workflow started...")

    @Slot(bool, str)
    def _on_workflow_finished(self, success: bool, message: str) -> None:
        """Handle workflow finished."""
        logger.info("Workflow finished (success=%s): %s", success, message)
        self.processing_finished.emit()
        if self._status_manager:
            if success:
                self._status_manager.show_message("Processing workflow completed")
            else:
                self._status_manager.show_message(f"Processing failed: {message}")

    @Slot()
    def _on_merge_started(self) -> None:
        """Handle merge started."""
        logger.info("Merge started")
        if self._status_manager:
            self._status_manager.show_message("Merging processing results...")

    @Slot(bool, str)
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

    def _on_status_message(self, message: str) -> None:
        """Show status message in main window status bar."""
        if self._status_manager:
            self._status_manager.show_message(message)

    # ------------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------------
    def is_processing(self) -> bool:
        """Return whether processing is active."""
        return False  # Simplified - main window handles this now

    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for coordinating background operations."""
        self._status_manager = status_manager
        # Connect workflow panel status messages to main window status manager
        if self._status_connection:
            self._config_panel.status_message.disconnect(self._status_connection)
        self._status_connection = self._config_panel.status_message.connect(
            self._status_manager.show_message
        )
