"""Status bar components for pyama-air GUI."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLabel, QStatusBar

logger = logging.getLogger(__name__)


# =============================================================================
# STATUS MANAGER
# =============================================================================


class StatusManager(QObject):
    """Status manager for showing user-friendly messages."""

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
# STATUS BAR
# =============================================================================


class StatusBar(QStatusBar):
    """Status bar for displaying status messages only."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Set up the status bar UI components."""
        # Main status label
        self._status_label = QLabel("Ready")
        self.addWidget(self._status_label)

    def _connect_signals(self) -> None:
        """Connect signals for the status bar."""
        pass

    # ------------------------------------------------------------------------
    # STATUS METHODS
    # ------------------------------------------------------------------------
    def show_status_message(self, message: str) -> None:
        """Show a status message."""
        self._status_label.setText(message)

    def clear_status(self) -> None:
        """Clear the status message."""
        self._status_label.setText("Ready")
