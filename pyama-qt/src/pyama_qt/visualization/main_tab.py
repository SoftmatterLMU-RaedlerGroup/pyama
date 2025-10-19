"""Visualization page composed of project, image, and trace panels."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_qt.visualization.image import ImagePanel
from pyama_qt.visualization.load import LoadPanel
from pyama_qt.visualization.trace import TracePanel

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN VISUALIZATION TAB
# =============================================================================


class VisualizationTab(QWidget):
    """
    Embeddable visualization page comprising consolidated project, image, and trace panels.
    This tab orchestrates the interactions between the panels.
    """

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_manager = None
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # STATUS MANAGER INTEGRATION
    # ------------------------------------------------------------------------
    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for coordinating background operations."""
        self._status_manager = status_manager

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create and arrange the UI panels."""
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
        """Connect all signals between panels."""
        # Project Panel -> Image Panel
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
        """Connect visualization-related status signals."""
        # Connect image loading status signals
        self._image_panel.loading_started.connect(self._on_visualization_started)
        self._image_panel.loading_finished.connect(self._on_visualization_finished)
        self._load_panel.project_loading_started.connect(
            self._on_project_loading_started
        )
        self._load_panel.project_loading_finished.connect(
            self._on_project_loading_finished
        )

    # ------------------------------------------------------------------------
    # STATUS MANAGER INTEGRATION
    # ------------------------------------------------------------------------
    def _on_visualization_started(self) -> None:
        """Handle visualization started."""
        if self._status_manager:
            self._status_manager.show_message("Loading visualization data...")

    def _on_visualization_finished(self, success: bool, message: str) -> None:
        """Handle visualization finished."""
        if self._status_manager:
            if success:
                self._status_manager.show_message("Visualization data loaded")
            else:
                self._status_manager.show_message(
                    f"Failed to load visualization: {message}"
                )

    def _on_project_loading_started(self) -> None:
        """Handle project loading started."""
        if self._status_manager:
            self._status_manager.show_message("Loading project data...")

    def _on_project_loading_finished(self, success: bool, message: str) -> None:
        """Handle project loading finished."""
        if self._status_manager:
            if success:
                self._status_manager.show_message("Project data loaded")
            else:
                self._status_manager.show_message(f"Failed to load project: {message}")

    # ------------------------------------------------------------------------
    # FUTURE STATUS BAR INTEGRATION
    # ------------------------------------------------------------------------
    def _setup_status_bar_connections(self, main_window_status_bar):
        """
        Example of connecting panels to a central status bar.

        This method shows how to connect all panels to a main window status bar
        if one becomes available in the future.
        """

        # Connect error messages with longer display time
        self._load_panel.error_message.connect(
            lambda msg: main_window_status_bar.showMessage(f"Error: {msg}", 5000)
        )
        self._image_panel.error_message.connect(
            lambda msg: main_window_status_bar.showMessage(f"Error: {msg}", 5000)
        )
