"""Analysis tab composed of data, fitting quality, and results panels."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtWidgets import QHBoxLayout, QWidget

from .data import DataPanel
from .fitting import FittingPanel
from .results import ResultsPanel

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
        self._build_ui()
        self._connect_panels()

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create and arrange the UI panels."""
        layout = QHBoxLayout(self)

        # Create panels
        self.data_panel = DataPanel(self)  # Data loading and visualization
        self.fitting_panel = FittingPanel(self)  # Fitting quality display
        self.results_panel = ResultsPanel(self)  # Parameter analysis

        # Arrange panels horizontally
        layout.addWidget(self.data_panel, 1)  # Data on the left
        layout.addWidget(self.fitting_panel, 1)  # Fitting quality in the middle
        layout.addWidget(self.results_panel, 1)  # Parameter analysis on the right

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
        self.data_panel.rawDataChanged.connect(self.fitting_panel.on_raw_data_changed)
        self.data_panel.rawCsvPathChanged.connect(
            self.fitting_panel.on_raw_csv_path_changed
        )

        # When fitting is complete from the data panel, send results to the fitting panel
        self.data_panel.fittingCompleted.connect(
            self.fitting_panel.on_fitting_completed
        )

    # ------------------------------------------------------------------------
    # DATA PANEL -> RESULTS PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_data_to_results(self) -> None:
        """Connect data panel signals to results panel."""
        # When fitting is complete from the data panel, send results to the results panel
        self.data_panel.fittingCompleted.connect(
            self.results_panel.on_fitting_completed
        )

        # When fitted results are loaded from file, send them to the results panel
        self.data_panel.fittedResultsLoaded.connect(
            self.results_panel.on_fitting_completed
        )

        # When fitted results are loaded from file, also send them to the fitting panel
        self.data_panel.fittedResultsLoaded.connect(
            self.fitting_panel.on_fitted_results_changed
        )

    # ------------------------------------------------------------------------
    # FITTING PANEL -> DATA PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_fitting_to_data(self) -> None:
        """Connect fitting panel signals to data panel."""
        # Allow fitting panel to request a random cell for visualization
        self.fitting_panel.shuffle_requested.connect(
            lambda: self.fitting_panel.on_shuffle_requested(
                self.data_panel.get_random_cell
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
        self.results_panel.results_loaded.connect(
            self.fitting_panel.on_fitted_results_changed
        )
