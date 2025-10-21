"""Processing tab - orchestrates workflow and merge functionality."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_pro.processing.merge import MergePanel
from pyama_pro.processing.workflow import WorkflowPanel

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN PROCESSING TAB
# =============================================================================


class ProcessingTab(QWidget):
    """Processing page orchestrator - connects workflow and merge panels.

    This tab serves as the main container for processing functionality,
    coordinating between the workflow configuration panel and the merge panel.
    It handles signal routing and status updates for both sub-components.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    processing_started = Signal()  # Emitted when any processing operation starts
    processing_finished = Signal()  # Emitted when any processing operation finishes

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None):
        """Initialize the processing tab.

        Args:
            parent: Parent widget (default: None)
        """
        super().__init__(parent)
        self._status_manager = None
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI BUILDING
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create the user interface layout with workflow and merge panels."""
        layout = QHBoxLayout(self)

        self._workflow_panel = WorkflowPanel(self)
        self._merge_panel = MergePanel(self)

        # Add panels with 2:1 ratio (workflow gets more space)
        layout.addWidget(self._workflow_panel, 2)
        layout.addWidget(self._merge_panel, 1)

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals between panels and handlers."""
        self._connect_status_signals()

    def _connect_status_signals(self) -> None:
        """Connect semantic signals from panels for status updates.

        This method connects all the semantic signals from child panels
        to their respective handlers, ensuring proper status propagation
        and user feedback.
        """
        # Workflow panel signals
        self._workflow_panel.workflow_started.connect(self._on_workflow_started)
        self._workflow_panel.workflow_finished.connect(self._on_workflow_finished)
        self._workflow_panel.microscopy_loading_started.connect(
            self._on_microscopy_loading_started
        )
        self._workflow_panel.microscopy_loading_finished.connect(
            self._on_microscopy_loading_finished
        )

        # Merge panel signals
        self._merge_panel.merge_started.connect(self._on_merge_started)
        self._merge_panel.merge_finished.connect(self._on_merge_finished)
        self._merge_panel.samples_loading_started.connect(
            self._on_samples_loading_started
        )
        self._merge_panel.samples_loading_finished.connect(
            self._on_samples_loading_finished
        )
        self._merge_panel.samples_saving_started.connect(
            self._on_samples_saving_started
        )
        self._merge_panel.samples_saving_finished.connect(
            self._on_samples_saving_finished
        )

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot()
    def _on_workflow_started(self) -> None:
        """Handle workflow started event.

        Logs the event and propagates the signal to parent components.
        Updates the status message if a status manager is available.
        """
        logger.info("Workflow started")
        self.processing_started.emit()
        if self._status_manager:
            self._status_manager.show_message("Processing workflow started...")

    @Slot(bool, str)
    def _on_workflow_finished(self, success: bool, message: str) -> None:
        """Handle workflow finished event.

        Args:
            success: Whether the workflow completed successfully
            message: Status message from the workflow
        """
        logger.info("Workflow finished (success=%s): %s", success, message)
        self.processing_finished.emit()
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Processing failed: {message}")

    @Slot()
    def _on_merge_started(self) -> None:
        """Handle merge started event.

        Logs the event and updates the status message if a status manager is available.
        """
        logger.info("Merge started")
        if self._status_manager:
            self._status_manager.show_message("Merging processing results...")

    @Slot(bool, str)
    def _on_merge_finished(self, success: bool, message: str) -> None:
        """Handle merge finished event.

        Args:
            success: Whether the merge completed successfully
            message: Status message from the merge operation
        """
        logger.info("Merge finished (success=%s): %s", success, message)
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Merge failed: {message}")

    @Slot()
    def _on_microscopy_loading_started(self) -> None:
        """Handle microscopy loading started event.

        Logs the event and updates the status message if a status manager is available.
        """
        logger.info("Microscopy loading started")
        if self._status_manager:
            self._status_manager.show_message("Loading ND2 file...")

    @Slot(bool, str)
    def _on_microscopy_loading_finished(self, success: bool, message: str) -> None:
        """Handle microscopy loading finished event.

        Args:
            success: Whether the loading completed successfully
            message: Status message from the loading operation
        """
        logger.info("Microscopy loading finished (success=%s): %s", success, message)
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to load ND2: {message}")

    @Slot()
    def _on_samples_loading_started(self) -> None:
        """Handle samples loading started event.

        Logs the event and updates the status message if a status manager is available.
        """
        logger.info("Samples loading started")
        if self._status_manager:
            self._status_manager.show_message("Loading samples...")

    @Slot(bool, str)
    def _on_samples_loading_finished(self, success: bool, message: str) -> None:
        """Handle samples loading finished event.

        Args:
            success: Whether the loading completed successfully
            message: Status message from the loading operation
        """
        logger.info("Samples loading finished (success=%s): %s", success, message)
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to load samples: {message}")

    @Slot()
    def _on_samples_saving_started(self) -> None:
        """Handle samples saving started event.

        Logs the event and updates the status message if a status manager is available.
        """
        logger.info("Samples saving started")
        if self._status_manager:
            self._status_manager.show_message("Saving samples...")

    @Slot(bool, str)
    def _on_samples_saving_finished(self, success: bool, message: str) -> None:
        """Handle samples saving finished event.

        Args:
            success: Whether the saving completed successfully
            message: Status message from the saving operation
        """
        logger.info("Samples saving finished (success=%s): %s", success, message)
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to save samples: {message}")

    # ------------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------------
    def is_processing(self) -> bool:
        """Return whether processing is active.

        Returns:
            bool: Always returns False as the main window handles this now
        """
        return False  # Simplified - main window handles this now

    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for coordinating background operations.

        Args:
            status_manager: Status manager instance for displaying messages
        """
        self._status_manager = status_manager
