"""Visualization page composed of project, image, and trace panels."""

import logging
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QStatusBar

from pyama_qt.visualization.controller import VisualizationController
from pyama_qt.visualization.panels import ImagePanel, ProjectPanel, TracePanel
from pyama_qt.visualization.state import (
    VisualizationState,
    ProjectLoadRequest,
    VisualizationRequest,
    TraceSelectionRequest,
)
from pyama_qt.ui import BasePage

logger = logging.getLogger(__name__)


class VisualizationPage(BasePage[VisualizationState]):
    """Embeddable visualization page comprising project, image, and trace panels."""

    def __init__(self, parent=None):
        self.controller = VisualizationController()
        super().__init__(parent)
        self.set_state(self.controller.current_state())
        logger.info("PyAMA Visualization Page loaded")

    # BasePage hooks -------------------------------------------------------
    def build(self) -> None:
        self._status_bar = QStatusBar(self)
        layout = QHBoxLayout(self)

        self.project_panel = ProjectPanel(self)
        self.image_panel = ImagePanel(self)
        self.trace_panel = TracePanel(self)

        layout.addWidget(self.project_panel, 1)
        layout.addWidget(self.image_panel, 1)
        layout.addWidget(self.trace_panel, 1)
        layout.addWidget(self._status_bar)

    def bind(self) -> None:
        # Connect controller signals
        self.controller.state_changed.connect(self.set_state)
        self.controller.project_loaded.connect(self._on_project_loaded)
        self.controller.fov_data_ready.connect(self._on_fov_data_ready)
        self.controller.trace_data_ready.connect(self._on_trace_data_ready)
        self.controller.error_occurred.connect(self._on_error_occurred)

        # Connect panel signals to controller
        self.project_panel.project_load_requested.connect(self._on_project_load_requested)
        self.project_panel.visualization_requested.connect(self._on_visualization_requested)
        self.trace_panel.trace_selection_changed.connect(self._on_trace_selection_changed)

        # Connect inter-panel communication
        self.trace_panel.active_trace_changed.connect(self.image_panel.set_active_trace)

    def set_state(self, state: VisualizationState) -> None:
        super().set_state(state)
        
        # Update status bar
        if state.error_message:
            self._status_bar.showMessage(f"Error: {state.error_message}")
        else:
            self._status_bar.showMessage(state.status_message or "Ready")

        # Update panels with new state
        self.project_panel.set_state(state)
        self.image_panel.set_state(state)
        self.trace_panel.set_state(state)

    # Event handlers -------------------------------------------------------
    def _on_project_load_requested(self, project_path: Path) -> None:
        """Handle project load request from project panel."""
        request = ProjectLoadRequest(project_path=project_path)
        self.controller.load_project(request)

    def _on_visualization_requested(self, fov_idx: int, selected_channels: list[str]) -> None:
        """Handle visualization request from project panel."""
        request = VisualizationRequest(fov_idx=fov_idx, selected_channels=selected_channels)
        self.controller.start_visualization(request)

    def _on_trace_selection_changed(self, trace_id: str | None) -> None:
        """Handle trace selection change from trace panel."""
        request = TraceSelectionRequest(trace_id=trace_id)
        self.controller.set_active_trace(request)

    def _on_project_loaded(self, project_data: dict) -> None:
        """Handle project loaded signal from controller."""
        # Project data is already in state, panels will update automatically
        pass

    def _on_fov_data_ready(self, fov_idx: int) -> None:
        """Handle FOV data ready signal from controller."""
        # Image data is already in state, image panel will update automatically
        pass

    def _on_trace_data_ready(self, trace_data: dict) -> None:
        """Handle trace data ready signal from controller."""
        # Trace data is already in state, trace panel will update automatically
        pass

    def _on_error_occurred(self, message: str) -> None:
        """Handle error from controller."""
        QMessageBox.critical(self, "Visualization Error", message)
