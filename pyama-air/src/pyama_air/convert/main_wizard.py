"""Main convert wizard for pyama-air GUI."""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QWidget, QWizard

from pyama_air.convert.pages import (
    ConfigurationPage,
    ExecutionPage,
    FileSelectionPage,
)
from pyama_air.types.convert import ConvertConfig, ConvertPageData

logger = logging.getLogger(__name__)


# =============================================================================
# CONVERT WIZARD
# =============================================================================


class ConvertWizard(QWizard):
    """Wizard for converting microscopy files to OME-TIFF format."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    convert_started = Signal()
    convert_finished = Signal(bool, str)  # success, message

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the convert wizard."""
        super().__init__(parent)
        self.setWindowTitle("PyAMA Convert Wizard")
        self.setModal(True)
        self.resize(500, 350)

        # Remove default wizard background image
        self.setWizardStyle(QWizard.ModernStyle)

        # Data storage
        self._page_data = ConvertPageData()

        # Create wizard pages
        self._create_pages()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # PAGE CREATION
    # ------------------------------------------------------------------------
    def _create_pages(self) -> None:
        """Create all wizard pages."""
        self.addPage(FileSelectionPage(self))
        self.addPage(ConfigurationPage(self))
        self.addPage(ExecutionPage(self))

    def _connect_signals(self) -> None:
        """Connect wizard signals."""
        self.currentIdChanged.connect(self._on_page_changed)

    @Slot(int)
    def _on_page_changed(self, page_id: int) -> None:
        """Handle page changes."""
        logger.debug("Convert wizard page changed to: %d", page_id)

    # ------------------------------------------------------------------------
    # DATA ACCESS
    # ------------------------------------------------------------------------
    def get_convert_config(self) -> ConvertConfig | None:
        """Get the configured convert configuration."""
        return ConvertConfig.from_page_data(self._page_data)

    def get_page_data(self) -> ConvertPageData:
        """Get the current page data."""
        return self._page_data

