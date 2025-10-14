"""Visualization page composed of project, image, and trace panels."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging

from PySide6.QtWidgets import QHBoxLayout, QWidget

from .image import ImagePanel
from .project import ProjectPanel
from .trace import TracePanel

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
        self._connect_panels()

    # ------------------------------------------------------------------------
    # STATUS MODEL INTEGRATION
    # ------------------------------------------------------------------------
    def set_status_model(self, status_model):
        """Connect status model to handle processing state changes."""
        status_model.is_processing_changed.connect(self._on_processing_changed)

    def _on_processing_changed(self, is_processing):
        """Handle processing state changes from other tabs."""
        logger.debug(
            "UI Event: Processing state changed - is_processing=%s", is_processing
        )
        # Disable all visualization panels during processing
        self._project_panel.setEnabled(not is_processing)
        self._image_panel.setEnabled(not is_processing)
        self._trace_panel.setEnabled(not is_processing)

        # Update status bar if available
        if is_processing:
            if self.window() and hasattr(self.window(), "statusBar"):
                self.window().statusBar().showMessage(
                    "Processing is running, visualization is disabled."
                )
        else:
            if self.window() and hasattr(self.window(), "statusBar"):
                self.window().statusBar().showMessage("Processing finished.", 3000)

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create and arrange the UI panels."""
        layout = QHBoxLayout(self)

        # Create panels
        self._project_panel = ProjectPanel(self)  # Project loading and configuration
        self._image_panel = ImagePanel(self)  # Image display and interaction
        self._trace_panel = TracePanel(self)  # Trace data visualization

        # Arrange panels with appropriate spacing
        layout.addWidget(self._project_panel, 1)  # Project panel - normal width
        layout.addWidget(self._image_panel, 2)  # Image panel - more space for display
        layout.addWidget(self._trace_panel, 1)  # Trace panel - moderate width

        # Note: A central status bar can be added to the main window if needed
        # and connected via signals from the panels.

    # ------------------------------------------------------------------------
    # PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_panels(self) -> None:
        """
        Wire up the signals and slots between the panels to create the application logic.

        Signal flow pattern:
        - Project Panel -> Image Panel: Visualization requests with FOV and channels
        - Image Panel -> Trace Panel: FOV data loading notifications
        - Trace Panel -> Image Panel: Trace selection for highlighting
        - Image Panel -> Trace Panel: Cell picking events
        """
        self._connect_project_to_image()
        self._connect_image_to_trace()
        self._connect_trace_to_image()
        self._connect_status_signals()

    # ------------------------------------------------------------------------
    # PROJECT PANEL -> IMAGE PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_project_to_image(self) -> None:
        """Connect project panel signals to image panel."""
        # When a project is loaded and user requests visualization, start image loading
        self._project_panel.visualization_requested.connect(
            self._image_panel.on_visualization_requested
        )

        # Connect loading state to show progress bar
        self._image_panel.loading_state_changed.connect(self._project_panel.set_loading)

    # ------------------------------------------------------------------------
    # IMAGE PANEL -> TRACE PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_image_to_trace(self) -> None:
        """Connect image panel signals to trace panel."""
        # When FOV image data is loaded, notify the trace panel to load corresponding trace data
        self._image_panel.fov_data_loaded.connect(self._trace_panel.on_fov_data_loaded)

    # ------------------------------------------------------------------------
    # TRACE PANEL -> IMAGE PANEL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_trace_to_image(self) -> None:
        """Connect trace panel signals to image panel."""
        # When a trace is selected in the table, highlight it on the image
        self._trace_panel.active_trace_changed.connect(
            self._image_panel.on_active_trace_changed
        )

        # When a cell is picked on the image, select it in the trace panel
        self._image_panel.cell_selected.connect(self._trace_panel.on_cell_selected)

        # When a trace overlay is right-clicked, toggle its quality status
        self._image_panel.trace_quality_toggled.connect(
            self._trace_panel.on_trace_quality_toggled
        )

        # When trace positions are updated, draw overlays on the image
        self._trace_panel.positions_updated.connect(
            self._image_panel.on_trace_positions_updated
        )

        # When frame changes in image panel, update trace overlays
        self._image_panel.frame_changed.connect(self._trace_panel.on_frame_changed)

    # ------------------------------------------------------------------------
    # STATUS SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_status_signals(self) -> None:
        """Connect visualization-related status signals."""
        # Connect image loading status signals
        self._image_panel.loading_started.connect(self._on_visualization_started)
        self._image_panel.loading_finished.connect(self._on_visualization_finished)
        self._project_panel.project_loading_started.connect(self._on_project_loading_started)
        self._project_panel.project_loading_finished.connect(self._on_project_loading_finished)

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
                self._status_manager.show_message(f"Failed to load visualization: {message}")
                
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
                
    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for coordinating background operations."""
        self._status_manager = status_manager

    # ------------------------------------------------------------------------
    # FUTURE STATUS BAR INTEGRATION
    # ------------------------------------------------------------------------
    def _setup_status_bar_connections(self, main_window_status_bar):
        """
        Example of connecting panels to a central status bar.

        This method shows how to connect all panels to a main window status bar
        if one becomes available in the future.
        """
        # Connect status messages
        self._project_panel.status_message.connect(main_window_status_bar.showMessage)
        self._image_panel.status_message.connect(main_window_status_bar.showMessage)
        self._trace_panel.status_message.connect(main_window_status_bar.showMessage)

        # Connect error messages with longer display time
        self._project_panel.error_message.connect(
            lambda msg: main_window_status_bar.showMessage(f"Error: {msg}", 5000)
        )
        self._image_panel.error_message.connect(
            lambda msg: main_window_status_bar.showMessage(f"Error: {msg}", 5000)
        )
