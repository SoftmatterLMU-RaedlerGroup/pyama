"""Analysis tab composed of data, fitting quality, and results panels."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_qt.analysis.data import DataPanel
from pyama_qt.analysis.parameter import ParameterPanel
from pyama_qt.analysis.quality import QualityPanel

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN ANALYSIS TAB
# =============================================================================


class AnalysisTab(QWidget):
    """
    Embeddable analysis page comprising data, fitting quality, and parameter analysis panels.
    This tab orchestrates the interactions between the panels.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    processing_started = Signal()  # When fitting starts
    processing_finished = Signal()  # When fitting finishes

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_manager = None
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals between panels."""
        # Data Panel -> Fitting Panel
        self._data_panel.raw_data_changed.connect(
            self._quality_panel.on_raw_data_changed
        )
        self._data_panel.fitting_completed.connect(
            self._quality_panel.on_fitting_completed
        )

        # Data Panel -> Results Panel
        self._data_panel.fitting_completed.connect(
            self._parameter_panel.on_fitting_completed
        )
        self._data_panel.fitted_results_loaded.connect(
            self._parameter_panel.on_fitting_completed
        )
        self._data_panel.fitted_results_loaded.connect(
            self._quality_panel.on_fitted_results_changed
        )

        # Fitting Panel -> Data Panel
        self._quality_panel.shuffle_requested.connect(
            lambda: self._quality_panel.on_shuffle_requested(
                self._data_panel.get_random_cell
            )
        )

        # Results Panel -> Fitting Panel
        self._parameter_panel.results_loaded.connect(
            self._quality_panel.on_fitted_results_changed
        )

        # Status signals
        self._connect_status_signals()

    def _connect_status_signals(self) -> None:
        """Connect semantic signals for status updates."""
        # File saved signals
        self._data_panel.file_saved.connect(self._on_file_saved)

        # Fitting and data loading status signals
        self._data_panel.fitting_started.connect(self._on_fitting_started)
        self._data_panel.fitting_finished.connect(self._on_fitting_finished)
        self._data_panel.fitting_completed.connect(self._on_fitting_completed)
        self._data_panel.data_loading_started.connect(self._on_data_loading_started)
        self._data_panel.data_loading_finished.connect(self._on_data_loading_finished)

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create and arrange the UI panels."""
        layout = QHBoxLayout(self)

        # Create panels
        self._data_panel = DataPanel(self)
        self._quality_panel = QualityPanel(self)
        self._parameter_panel = ParameterPanel(self)

        # Arrange panels horizontally
        layout.addWidget(self._data_panel, 1)
        layout.addWidget(self._quality_panel, 1)
        layout.addWidget(self._parameter_panel, 1)

    # ------------------------------------------------------------------------
    # STATUS MANAGER INTEGRATION
    # ------------------------------------------------------------------------
    @Slot()
    def _on_fitting_started(self) -> None:
        """Handle fitting started."""
        self.processing_started.emit()
        if self._status_manager:
            self._status_manager.show_message("Fitting analysis models...")

    @Slot(bool, str)
    def _on_fitting_finished(self, success: bool, message: str) -> None:
        """Handle fitting finished."""
        self.processing_finished.emit()
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Fitting failed: {message}")

    @Slot()
    def _on_fitting_completed(self, results) -> None:
        """Handle fitting completed."""
        self.processing_finished.emit()
        if self._status_manager:
            self._status_manager.show_message("Fitting completed")

    @Slot()
    def _on_data_loading_started(self) -> None:
        """Handle data loading started."""
        if self._status_manager:
            self._status_manager.show_message("Loading analysis data...")

    @Slot(bool, str)
    def _on_data_loading_finished(self, success: bool, message: str) -> None:
        """Handle data loading finished."""
        if self._status_manager:
            if success:
                self._status_manager.show_message("Analysis data loaded")
            else:
                self._status_manager.show_message(f"Failed to load data: {message}")

    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for coordinating background operations."""
        self._status_manager = status_manager

    @Slot(str, str)
    def _on_file_saved(self, filename: str, directory: str) -> None:
        """Handle file saved notifications."""
        if self._status_manager:
            self._status_manager.show_message(f"{filename} saved to {directory}")
