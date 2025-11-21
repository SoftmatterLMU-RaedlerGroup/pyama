"""Main workflow wizard for pyama-air GUI."""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QWidget, QWizard

from pyama_air.workflow.pages import (
    ChannelConfigurationPage,
    ExecutionPage,
    FeatureSelectionPage,
    FileSelectionPage,
    ParameterConfigurationPage,
)
from pyama_air.types.workflow import WorkflowConfig, WorkflowPageData

logger = logging.getLogger(__name__)


# =============================================================================
# WORKFLOW WIZARD
# =============================================================================


class WorkflowWizard(QWizard):
    """Wizard for configuring and executing PyAMA workflows."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    workflow_started = Signal()
    workflow_finished = Signal(bool, str)  # success, message

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the workflow wizard."""
        super().__init__(parent)
        self.setWindowTitle("PyAMA Workflow Wizard")
        self.setModal(True)
        self.resize(500, 600)

        # Remove default wizard background image
        self.setWizardStyle(QWizard.ModernStyle)

        # Data storage
        self._page_data = WorkflowPageData()
        self._channel_names: list[str] = []
        self._pc_features: list[str] = []
        self._fl_features: list[str] = []

        # Initialize feature discovery
        self._discover_features()

        # Create wizard pages
        self._create_pages()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # FEATURE DISCOVERY
    # ------------------------------------------------------------------------
    def _discover_features(self) -> None:
        """Discover available features from PyAMA core."""
        try:
            from pyama_core.processing.extraction.features import (
                list_fluorescence_features,
                list_phase_features,
            )

            self._pc_features = list_phase_features()
            self._fl_features = list_fluorescence_features()

            if not self._pc_features:
                logger.warning("No phase contrast features found, using default 'area'")
                self._pc_features = ["area"]

            if not self._fl_features:
                logger.warning(
                    "No fluorescence features found, using default 'intensity_total'"
                )
                self._fl_features = ["intensity_total"]

        except Exception as exc:
            logger.warning("Failed to discover features: %s, using defaults", exc)
            self._pc_features = ["area"]
            self._fl_features = ["intensity_total"]

    # ------------------------------------------------------------------------
    # PAGE CREATION
    # ------------------------------------------------------------------------
    def _create_pages(self) -> None:
        """Create all wizard pages."""
        self.addPage(FileSelectionPage(self))
        self.addPage(ChannelConfigurationPage(self))
        self.addPage(FeatureSelectionPage(self))
        self.addPage(ParameterConfigurationPage(self))
        self.addPage(ExecutionPage(self))

    def _connect_signals(self) -> None:
        """Connect wizard signals."""
        self.currentIdChanged.connect(self._on_page_changed)

    @Slot(int)
    def _on_page_changed(self, page_id: int) -> None:
        """Handle page changes."""
        logger.debug("Wizard page changed to: %d", page_id)

    # ------------------------------------------------------------------------
    # DATA ACCESS
    # ------------------------------------------------------------------------
    def get_workflow_config(self) -> WorkflowConfig | None:
        """Get the configured workflow configuration."""
        return WorkflowConfig.from_page_data(self._page_data)

    def get_page_data(self) -> WorkflowPageData:
        """Get the current page data."""
        return self._page_data
