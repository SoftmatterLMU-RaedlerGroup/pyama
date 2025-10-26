"""Analysis tab composed of data, fitting quality, and results panels."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_pro.analysis.data import DataPanel
from pyama_pro.analysis.parameter import ParameterPanel
from pyama_pro.analysis.quality import QualityPanel

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN ANALYSIS TAB
# =============================================================================


class AnalysisTab(QWidget):
    """Embeddable analysis page comprising data, fitting quality, and parameter analysis panels.

    This tab orchestrates the interactions between the panels, managing signal
    routing and status updates for the analysis workflow. It provides a
    unified interface for loading trace data, performing model fitting,
    and analyzing parameter distributions and fitting quality.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    processing_started = Signal()  # Emitted when fitting starts
    processing_finished = Signal()  # Emitted when fitting finishes

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the analysis tab.

        Args:
            parent: Parent widget (default: None)
        """
        super().__init__(parent)
        self._status_manager = None
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals between panels.

        Establishes the communication pathways between panels:
        - Data panel -> Quality panel: raw data changes and fitting completion
        - Data panel -> Parameter panel: fitting completion and results loading
        - Parameter panel -> Quality panel: results loading

        Also connects status signals for centralized status reporting.
        """
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

        # Results Panel -> Fitting Panel
        self._parameter_panel.results_loaded.connect(
            self._quality_panel.on_fitted_results_changed
        )

        # Status signals
        self._connect_status_signals()

    def _connect_status_signals(self) -> None:
        """Connect semantic signals for status updates.

        Connects all status signals from child panels to their respective
        handlers to provide centralized status reporting through the
        status manager.
        """
        # Fitting and data loading status signals
        self._data_panel.fitting_started.connect(self._on_fitting_started)
        self._data_panel.fitting_finished.connect(self._on_fitting_finished)
        self._data_panel.fitting_completed.connect(self._on_fitting_completed)
        self._data_panel.data_loading_started.connect(self._on_data_loading_started)
        self._data_panel.data_loading_finished.connect(self._on_data_loading_finished)

        # Plot saving signals
        self._parameter_panel.plot_saved.connect(self._on_plot_saved)

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create and arrange the UI panels.

        Creates a horizontal layout with three panels of equal width:
        1. Data panel for loading CSV files and plotting traces
        2. Quality panel for visualizing fitting diagnostics
        3. Parameter panel for analyzing parameter distributions
        """
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
        """Handle fitting started event.

        Logs the event, emits the processing_started signal, and updates
        the status message if a status manager is available.
        """
        self.processing_started.emit()
        if self._status_manager:
            self._status_manager.show_message("Fitting analysis models...")

    @Slot(bool, str)
    def _on_fitting_finished(self, success: bool, message: str) -> None:
        """Handle fitting finished event.

        Args:
            success: Whether the fitting completed successfully
            message: Status message from the fitting process
        """
        self.processing_finished.emit()
        if self._status_manager:
            if success:
                if message:  # Only show message if it's not empty
                    self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Fitting failed: {message}")

    @Slot()
    def _on_fitting_completed(self, results) -> None:
        """Handle fitting completed event.

        Args:
            results: Results from the fitting process
        """
        self.processing_finished.emit()
        if self._status_manager:
            self._status_manager.show_message("Fitting completed successfully")

    @Slot()
    def _on_data_loading_started(self) -> None:
        """Handle data loading started event.

        Logs the event and updates the status message if a status
        manager is available.
        """
        if self._status_manager:
            self._status_manager.show_message("Loading analysis data...")

    @Slot(bool, str)
    def _on_data_loading_finished(self, success: bool, message: str) -> None:
        """Handle data loading finished event.

        Args:
            success: Whether the data loaded successfully
            message: Status message from the data loading
        """
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to load data: {message}")

    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for coordinating background operations.

        Args:
            status_manager: Status manager instance for displaying messages
        """
        self._status_manager = status_manager

    @Slot(str, str)
    def _on_plot_saved(self, filename: str, directory: str) -> None:
        """Handle plot saved notifications.

        Args:
            filename: Name of the saved plot file
            directory: Directory where the plot was saved
        """
        if self._status_manager:
            self._status_manager.show_message(f"{filename} saved to {directory}")
