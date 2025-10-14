"""Analysis tab composed of data, fitting quality, and results panels."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_qt.analysis.data import DataPanel
from pyama_qt.analysis.fitting import FittingPanel
from pyama_qt.analysis.results import ResultsPanel

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
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_manager = None
        self._build_ui()
        self._connect_panels()

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create and arrange the UI panels."""
        layout = QHBoxLayout(self)

        # Create panels
        self._data_panel = DataPanel(self)  # Data loading and visualization
        self._fitting_panel = FittingPanel(self)  # Fitting quality display
        self._results_panel = ResultsPanel(self)  # Parameter analysis

        # Arrange panels horizontally
        layout.addWidget(self._data_panel, 1)  # Data on the left
        layout.addWidget(self._fitting_panel, 1)  # Fitting quality in the middle
        layout.addWidget(self._results_panel, 1)  # Parameter analysis on the right

        # Note: The status bar can be part of the main window, but for now,
        # we let panels manage their own status. If a central status bar is needed,
        # we can emit signals from the panels.

    # ------------------------------------------------------------------------
    # PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_panels(self) -> None:
        """
        Wire up the signals and slots between the panels to create the application logic.

        Signal flow pattern:
        - Data Panel -> Fitting Panel: Raw data and fitting notifications
        - Data Panel -> Results Panel: Fitting completion notifications
        - Fitting Panel -> Data Panel: Cell selection and shuffle requests
        - Fitting Panel -> Data Panel: Cell visualization feedback
        - Results Panel -> Fitting Panel: External fitted results loading
        """
        self._connect_data_to_fitting()
        self._connect_data_to_results()
        self._connect_fitting_to_data()
        self._connect_results_to_fitting()

    # ------------------------------------------------------------------------
    # DATA PANEL -> FITTING PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_data_to_fitting(self) -> None:
        """Connect data panel signals to fitting panel."""
        # When new data is loaded, notify the fitting panel
        self._data_panel.raw_data_changed.connect(
            self._fitting_panel.on_raw_data_changed
        )
        self._data_panel.raw_csv_path_changed.connect(
            self._fitting_panel.on_raw_csv_path_changed
        )

        # When fitting is complete from the data panel, send results to the fitting panel
        self._data_panel.fitting_completed.connect(
            self._fitting_panel.on_fitting_completed
        )

    # ------------------------------------------------------------------------
    # DATA PANEL -> RESULTS PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_data_to_results(self) -> None:
        """Connect data panel signals to results panel."""
        # When fitting is complete from the data panel, send results to the results panel
        self._data_panel.fitting_completed.connect(
            self._results_panel.on_fitting_completed
        )

        # When fitted results are loaded from file, send them to the results panel
        self._data_panel.fitted_results_loaded.connect(
            self._results_panel.on_fitting_completed
        )

        # When fitted results are loaded from file, also send them to the fitting panel
        self._data_panel.fitted_results_loaded.connect(
            self._fitting_panel.on_fitted_results_changed
        )

    # ------------------------------------------------------------------------
    # FITTING PANEL -> DATA PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_fitting_to_data(self) -> None:
        """Connect fitting panel signals to data panel."""
        # Allow fitting panel to request a random cell for visualization
        self._fitting_panel.shuffle_requested.connect(
            lambda: self._fitting_panel.on_shuffle_requested(
                self._data_panel.get_random_cell
            )
        )

        # Note: Removed connection that highlighted cells in data panel when visualized in fitting panel
        # to keep the data panel plot static after CSV loading

    # ------------------------------------------------------------------------
    # RESULTS PANEL -> FITTING PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_results_to_fitting(self) -> None:
        """Connect results panel signals to fitting panel."""
        # When fitted results are loaded from a file, notify the fitting panel
        # so it can display the fit quality.
        self._results_panel.results_loaded.connect(
            self._fitting_panel.on_fitted_results_changed
        )

        # Connect fitting status signals
        self._data_panel.fitting_started.connect(self._on_fitting_started)
        self._data_panel.fitting_completed.connect(self._on_fitting_completed)
        self._data_panel.data_loading_started.connect(self._on_data_loading_started)
        self._data_panel.data_loading_finished.connect(self._on_data_loading_finished)

    # ------------------------------------------------------------------------
    # STATUS MANAGER INTEGRATION
    # ------------------------------------------------------------------------
    @Slot()
    def _on_fitting_started(self) -> None:
        """Handle fitting started."""
        if self._status_manager:
            self._status_manager.show_message("Fitting analysis models...")

    @Slot()
    def _on_fitting_completed(self, results) -> None:
        """Handle fitting completed."""
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
