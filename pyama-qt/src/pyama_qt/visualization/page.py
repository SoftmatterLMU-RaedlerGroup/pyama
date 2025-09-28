"""Visualization page composed of project, image, and trace panels."""

import logging
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QStatusBar

from pyama_qt.visualization.controller import VisualizationController
from pyama_qt.visualization.requests import (
    ProjectLoadRequest,
    VisualizationRequest,
    TraceSelectionRequest,
)
from pyama_qt.visualization.panels import ProjectPanel, ImagePanel, TracePanel
from pyama_qt.ui import ModelBoundPage

logger = logging.getLogger(__name__)


class VisualizationPage(ModelBoundPage):
    """Embeddable visualization page comprising project, image, and trace panels."""

    def __init__(self, parent=None):
        self.controller = VisualizationController()
        super().__init__(parent)
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
        self.controller.error_occurred.connect(self._on_error_occurred)
        self._bind_models()

        # Connect panel signals to controller
        self.project_panel.project_load_requested.connect(
            self._on_project_load_requested
        )
        self.project_panel.visualization_requested.connect(
            self._on_visualization_requested
        )
        self.trace_panel.trace_selection_changed.connect(
            self._on_trace_selection_changed
        )

        # Connect inter-panel communication
        self.trace_panel.active_trace_changed.connect(self.image_panel.set_active_trace)

        # Set trace panel reference in controller for CSV path communication
        self.controller.set_trace_panel(self.trace_panel)

    def _bind_models(self) -> None:
        project_model = self.controller.project_model
        image_model = self.controller.image_model
        trace_table_model = self.controller.trace_table_model
        trace_feature_model = self.controller.trace_feature_model
        trace_selection_model = self.controller.trace_selection_model

        project_model.statusMessageChanged.connect(self._status_bar.showMessage)
        project_model.errorMessageChanged.connect(self._status_bar.showMessage)

        self.project_panel.set_models(project_model)
        self.image_panel.set_models(image_model, trace_selection_model)
        self.trace_panel.set_models(
            trace_table_model,
            trace_feature_model,
            trace_selection_model,
            project_model,
        )

    # Event handlers -------------------------------------------------------
    def _on_project_load_requested(self, project_path: Path) -> None:
        """Handle project load request from project panel."""
        self.controller.load_project(ProjectLoadRequest(project_path=project_path))

    def _on_visualization_requested(
        self, fov_idx: int, selected_channels: list[str]
    ) -> None:
        """Handle visualization request from project panel."""
        self.controller.start_visualization(
            VisualizationRequest(
                fov_idx=fov_idx,
                selected_channels=selected_channels,
            )
        )

    def _on_trace_selection_changed(self, trace_id: str | None) -> None:
        """Handle trace selection change from trace panel."""
        self.controller.set_active_trace(TraceSelectionRequest(trace_id=trace_id))

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
        logger.error(f"Visualization Error: {message}")
