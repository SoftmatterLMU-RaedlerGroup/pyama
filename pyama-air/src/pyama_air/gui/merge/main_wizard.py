"""Main merge wizard for pyama-air GUI."""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QWidget, QWizard

from pyama_air.gui.merge.pages import (
    ExecutionPage,
    FileSelectionPage,
    SampleConfigurationPage,
)
from pyama_air.types.merge import MergeConfig, MergePageData

logger = logging.getLogger(__name__)


# =============================================================================
# MERGE WIZARD
# =============================================================================


class MergeWizard(QWizard):
    """Wizard for configuring and executing PyAMA merges."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    merge_started = Signal()
    merge_finished = Signal(bool, str)  # success, message

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the merge wizard."""
        super().__init__(parent)
        self.setWindowTitle("PyAMA Merge Wizard")
        self.setModal(True)
        self.resize(800, 600)

        # Remove default wizard background image
        self.setWizardStyle(QWizard.ModernStyle)

        # Data storage
        self._page_data = MergePageData()

        # Create wizard pages
        self._create_pages()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # PAGE CREATION
    # ------------------------------------------------------------------------
    def _create_pages(self) -> None:
        """Create all wizard pages."""
        self.addPage(SampleConfigurationPage(self))
        self.addPage(FileSelectionPage(self))
        self.addPage(ExecutionPage(self))

    def _connect_signals(self) -> None:
        """Connect wizard signals."""
        self.currentIdChanged.connect(self._on_page_changed)

    @Slot(int)
    def _on_page_changed(self, page_id: int) -> None:
        """Handle page changes."""
        logger.debug("Merge wizard page changed to: %d", page_id)

    # ------------------------------------------------------------------------
    # DATA ACCESS
    # ------------------------------------------------------------------------
    def get_merge_config(self) -> MergeConfig | None:
        """Get the configured merge configuration."""
        return MergeConfig.from_page_data(self._page_data)

    def get_page_data(self) -> MergePageData:
        """Get the current page data."""
        return self._page_data
