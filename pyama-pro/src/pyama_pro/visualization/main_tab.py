"""Visualization page composed of project, image, and trace panels."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_pro.visualization.image import ImagePanel
from pyama_pro.visualization.load import LoadPanel
from pyama_pro.visualization.trace import TracePanel

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN VISUALIZATION TAB
# =============================================================================


class VisualizationTab(QWidget):
    """Embeddable visualization page comprising consolidated project, image, and trace panels.

    This tab orchestrates the interactions between the panels, managing signal
    routing and status updates for the visualization workflow. It provides a
    unified interface for loading project data, viewing microscopy images,
    and analyzing trace data.
    """

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the visualization tab.

        Args:
            parent: Parent widget (default: None)
        """
        super().__init__(parent)
        self._status_manager = None
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # STATUS MANAGER INTEGRATION
    # ------------------------------------------------------------------------
    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for coordinating background operations.

        Args:
            status_manager: Status manager instance for displaying messages
        """
        self._status_manager = status_manager

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create and arrange the UI panels.

        Creates a horizontal layout with three panels:
        1. Load panel (1/4 width) for project loading and FOV selection
        2. Image panel (1/2 width) for displaying microscopy images
        3. Trace panel (1/4 width) for displaying trace data
        """
        layout = QHBoxLayout(self)

        # Create panels
        self._load_panel = LoadPanel(self)
        self._image_panel = ImagePanel(self)
        self._trace_panel = TracePanel(self)

        # Arrange panels with appropriate spacing
        layout.addWidget(self._load_panel, 1)
        layout.addWidget(self._image_panel, 2)
        layout.addWidget(self._trace_panel, 1)

        # Note: A central status bar can be added to the main window if needed
        # and connected via signals from the panels.

    # ------------------------------------------------------------------------
    # PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals between panels.

        Establishes the communication pathways between panels:
        - Load panel -> Image panel: project data and FOV selection
        - Image panel -> Trace panel: FOV data and cell selection
        - Trace panel -> Image panel: active trace and position updates

        Also connects status signals for centralized status reporting.
        """
        # Project Panel -> Image Panel
        self._load_panel.cleanup_requested.connect(self._on_cleanup_requested)
        self._load_panel.visualization_requested.connect(
            self._image_panel.on_visualization_requested
        )
        self._image_panel.loading_state_changed.connect(self._load_panel.set_loading)

        # Image Panel -> Trace Panel
        self._image_panel.fov_data_loaded.connect(self._trace_panel.on_fov_data_loaded)

        # Trace Panel -> Image Panel
        self._trace_panel.active_trace_changed.connect(
            self._image_panel.on_active_trace_changed
        )
        self._image_panel.cell_selected.connect(self._trace_panel.on_cell_selected)
        self._image_panel.trace_quality_toggled.connect(
            self._trace_panel.on_trace_quality_toggled
        )
        self._trace_panel.positions_updated.connect(
            self._image_panel.on_trace_positions_updated
        )
        self._image_panel.frame_changed.connect(self._trace_panel.on_frame_changed)

        # Status signals
        self._connect_status_signals()

    def _connect_status_signals(self) -> None:
        """Connect visualization-related status signals.

        Connects all status signals from child panels to their respective
        handlers to provide centralized status reporting through the
        status manager.
        """
        # Image loading status signals removed - only show final trace loading result
        self._load_panel.project_loading_started.connect(
            self._on_project_loading_started
        )
        self._load_panel.project_loading_finished.connect(
            self._on_project_loading_finished
        )

        # Connect trace panel status signals
        self._trace_panel.trace_data_loaded.connect(self._on_trace_data_loaded)
        self._trace_panel.trace_data_saved.connect(self._on_trace_data_saved)

    # ------------------------------------------------------------------------
    # CLEANUP HANDLING
    # ------------------------------------------------------------------------
    def _on_cleanup_requested(self) -> None:
        """Handle cleanup request from load panel.

        Clears all existing plots and loaded traces before starting
        a new visualization session.
        """
        logger.debug("UI Event: Cleanup requested - clearing all panels")

        # Clear image panel (plots, cache, overlays)
        self._image_panel.clear_all()

        # Clear trace panel (traces, plots, data)
        self._trace_panel.clear()

        logger.debug("UI Action: All panels cleared successfully")

    # ------------------------------------------------------------------------
    # STATUS MANAGER INTEGRATION
    # ------------------------------------------------------------------------

    def _on_project_loading_started(self) -> None:
        """Handle project loading started event.

        Logs the event and updates the status message if a status manager is available.
        """
        if self._status_manager:
            self._status_manager.show_message("Loading project data...")

    def _on_project_loading_finished(self, success: bool, message: str) -> None:
        """Handle project loading finished event.

        Args:
            success: Whether the project loaded successfully
            message: Status message from the project loading
        """
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to load project: {message}")

    def _on_trace_data_loaded(self, success: bool, message: str) -> None:
        """Handle trace data loading finished event.

        Args:
            success: Whether the trace data loaded successfully
            message: Status message from the trace data loading
        """
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to load traces: {message}")

    def _on_trace_data_saved(self, success: bool, message: str) -> None:
        """Handle trace data saving finished event.

        Args:
            success: Whether the trace data saved successfully
            message: Status message from the trace data saving
        """
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to save traces: {message}")

    # ------------------------------------------------------------------------
    # FUTURE STATUS BAR INTEGRATION
    # ------------------------------------------------------------------------
    def _setup_status_bar_connections(self, main_window_status_bar) -> None:
        """Example of connecting panels to a central status bar.

        This method shows how to connect all panels to a main window status bar
        if one becomes available in the future. It demonstrates the pattern
        for connecting error messages with longer display times.

        Args:
            main_window_status_bar: Status bar widget from the main window
        """
        # Connect error messages with longer display time
        self._load_panel.error_message.connect(
            lambda msg: main_window_status_bar.showMessage(f"Error: {msg}", 5000)
        )
        self._image_panel.error_message.connect(
            lambda msg: main_window_status_bar.showMessage(f"Error: {msg}", 5000)
        )
