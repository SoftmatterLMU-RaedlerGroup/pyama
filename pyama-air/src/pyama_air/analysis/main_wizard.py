"""Main analysis wizard for pyama-air GUI."""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QWidget, QWizard

from pyama_air.analysis.pages import (
    ConfigurationPage,
    ExecutionPage,
    FileSelectionPage,
    ResultsPage,
    SavePage,
)
from pyama_air.types.analysis import AnalysisConfig, AnalysisPageData

logger = logging.getLogger(__name__)


# =============================================================================
# ANALYSIS WIZARD
# =============================================================================


class AnalysisWizard(QWizard):
    """Wizard for configuring and executing PyAMA analysis fitting."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    analysis_started = Signal()
    analysis_finished = Signal(bool, str)  # success, message

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the analysis wizard."""
        super().__init__(parent)
        self.setWindowTitle("PyAMA Analysis Wizard")
        self.setModal(True)
        self.resize(500, 350)

        # Remove default wizard background image
        self.setWizardStyle(QWizard.ModernStyle)

        # Data storage
        self._page_data = AnalysisPageData()
        self._available_models: list[str] = []

        # Initialize model discovery
        self._discover_models()

        # Create wizard pages
        self._create_pages()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # MODEL DISCOVERY
    # ------------------------------------------------------------------------
    def _discover_models(self) -> None:
        """Discover available models from PyAMA core."""
        try:
            from pyama_core.analysis.models import list_models

            self._available_models = list_models()

            if not self._available_models:
                logger.warning("No models found, using default 'maturation'")
                self._available_models = ["maturation"]

        except Exception as exc:
            logger.warning("Failed to discover models: %s, using defaults", exc)
            self._available_models = ["maturation"]

    # ------------------------------------------------------------------------
    # PAGE CREATION
    # ------------------------------------------------------------------------
    def _create_pages(self) -> None:
        """Create all wizard pages."""
        self.addPage(FileSelectionPage(self))
        self.addPage(ConfigurationPage(self))
        self.addPage(ExecutionPage(self))
        self.addPage(ResultsPage(self))
        self.addPage(SavePage(self))

    def _connect_signals(self) -> None:
        """Connect wizard signals."""
        self.currentIdChanged.connect(self._on_page_changed)

    @Slot(int)
    def _on_page_changed(self, page_id: int) -> None:
        """Handle page changes."""
        logger.debug("Analysis wizard page changed to: %d", page_id)

    # ------------------------------------------------------------------------
    # DATA ACCESS
    # ------------------------------------------------------------------------
    def get_analysis_config(self) -> AnalysisConfig | None:
        """Get the configured analysis configuration."""
        return AnalysisConfig.from_page_data(self._page_data)

    def get_page_data(self) -> AnalysisPageData:
        """Get the current page data."""
        return self._page_data

    def get_available_models(self) -> list[str]:
        """Get list of available models."""
        return self._available_models
