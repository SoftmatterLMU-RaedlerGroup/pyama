"""Controller coordinating visualization data loading and display."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal

from pyama_core.io.results_yaml import discover_processing_results

from pyama_qt.visualization.requests import (
    ProjectLoadRequest,
    VisualizationRequest,
    TraceSelectionRequest,
    FrameNavigationRequest,
    DataTypeChangeRequest,
)
from pyama_qt.visualization.models import (
    ProjectModel,
    ImageCacheModel,
    TraceTableModel,
    TraceFeatureModel,
    TraceSelectionModel,
    CellQuality,
)
from pyama_qt.services import WorkerHandle, start_worker

logger = logging.getLogger(__name__)


class VisualizationController(QObject):
    """Encapsulates visualization data loading and model management."""

    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project_model = ProjectModel()
        self.image_model = ImageCacheModel()
        self.trace_table_model = TraceTableModel()
        self.trace_feature_model = TraceFeatureModel()
        self.trace_selection_model = TraceSelectionModel()
        self._worker: WorkerHandle | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def current_state(self):
        raise AttributeError(
            "VisualizationController no longer exposes dataclass state"
        )

    def load_project(self, request: ProjectLoadRequest) -> None:
        """Load a PyAMA-Qt processing results project."""
        logger.debug("Loading project from %s", request.project_path)

        self.project_model.set_is_loading(True)
        self.project_model.set_error_message("")
        self.project_model.set_status_message(
            f"Loading project: {request.project_path.name}"
        )

        try:
            project_results = discover_processing_results(request.project_path)
            project_data = project_results.to_dict()
            available_channels = self._extract_available_channels(project_data)

            self.project_model.set_project_path(request.project_path)
            self.project_model.set_project_data(project_data)
            self.project_model.set_available_channels(available_channels)
            self.project_model.set_status_message(
                self._format_project_status(project_data)
            )
            self.project_model.set_is_loading(False)
        except Exception as exc:
            error_msg = self._format_project_error(request.project_path, exc)
            self.project_model.set_error_message(error_msg)
            self.project_model.set_status_message("Error loading project")
            self.project_model.set_is_loading(False)
            self.error_occurred.emit(error_msg)

    def start_visualization(self, request: VisualizationRequest) -> None:
        """Start visualization for a specific FOV."""
        if not self.project_model.project_data():
            self.error_occurred.emit("No project loaded")
            return

        if self._worker is not None:
            logger.warning("Visualization already running; canceling previous")
            self._cleanup_worker()

        logger.debug(
            "Starting visualization for FOV %d with channels %s",
            request.fov_idx,
            request.selected_channels,
        )

        self.image_model.remove_images()
        self.trace_table_model.reset_traces([])
        self.trace_feature_model.set_trace_features({})
        self.trace_selection_model.set_active_trace(None)

        self.project_model.set_status_message(f"Loading FOV {request.fov_idx:03d}...")
        self.project_model.set_is_loading(True)

        worker = _VisualizationWorker(
            project_data=self.project_model.project_data() or {},
            fov_idx=request.fov_idx,
            selected_channels=request.selected_channels,
        )
        worker.progress_updated.connect(self._on_worker_progress)
        worker.fov_data_loaded.connect(self._on_fov_data_loaded)
        worker.error_occurred.connect(self._on_worker_error)
        worker.finished.connect(self._on_worker_finished)

        handle = start_worker(
            worker,
            start_method="process_fov_data",
            finished_callback=self._cleanup_worker,
        )
        self._worker = handle

    def set_active_trace(self, request: TraceSelectionRequest) -> None:
        """Set the active trace for highlighting."""
        self.trace_selection_model.set_active_trace(request.trace_id)
        self.image_model.set_active_trace(request.trace_id)

    def navigate_frame(self, request: FrameNavigationRequest) -> None:
        """Navigate to a specific frame."""
        self.image_model.set_current_frame(request.frame_index)

    def change_data_type(self, request: DataTypeChangeRequest) -> None:
        """Change the displayed data type."""
        self.image_model.set_current_data_type(request.data_type)

    def cancel_loading(self) -> None:
        """Cancel any ongoing loading operation."""
        if self._worker is not None:
            self._cleanup_worker()
            self.project_model.set_is_loading(False)
            self.project_model.set_status_message("Loading canceled")

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------
    def _extract_available_channels(self, project_data: dict) -> list[str]:
        """Extract available channels from project data - return all available keys."""
        if not project_data.get("fov_data"):
            return []

        # Get first FOV to determine available channels
        first_fov_data = next(iter(project_data["fov_data"].values()))

        # Return all available channel keys
        channels = list(first_fov_data.keys())

        # Remove "traces" from the list since it's not a visualization channel
        if "traces" in channels:
            channels.remove("traces")

        return sorted(channels)

    def _format_project_status(self, project_data: dict) -> str:
        """Format a status message for the loaded project."""
        has_project_file = project_data.get("has_project_file", False)
        status = project_data.get("processing_status", "unknown")
        n_fov = project_data.get("n_fov", 0)

        if has_project_file:
            status_msg = f"Project loaded: {n_fov} FOVs, Status: {status.title()}"
            if status != "completed":
                status_msg += " ⚠️"
        else:
            status_msg = f"Project loaded: {n_fov} FOVs"

        return status_msg

    def _format_project_error(self, project_path: Path, exc: Exception) -> str:
        message = str(exc)
        if "No FOV directories found" in message:
            return (
                f"No data found in {project_path}.\n\n"
                "Make sure the directory contains FOV subdirectories"
            )
        return message

    def _on_worker_progress(self, message: str) -> None:
        """Handle progress updates from worker."""
        self.project_model.set_status_message(message)

    def _on_fov_data_loaded(
        self,
        fov_idx: int,
        image_map: dict[str, np.ndarray],
        traces: list[CellQuality],
        features: dict[str, dict[str, np.ndarray]],
        trace_positions: dict[str, dict[int, tuple[float, float]]],
        traces_path: Path | None = None,
    ) -> None:
        """Handle FOV data loaded notification."""
        logger.debug(
            f"FOV data loaded: {len(image_map)} images, {len(traces)} traces, {len(features)} features"
        )

        self.image_model.set_images(image_map)
        self.trace_table_model.reset_traces(traces)
        self.trace_feature_model.set_trace_features(features)
        self.image_model.set_trace_positions(trace_positions)

        # Pass the traces path to the trace panel if available
        if hasattr(self, "trace_panel") and traces_path:
            self.trace_panel.set_trace_csv_path(traces_path)

        # Automatically load trace CSV data if available
        if traces_path and traces_path.exists():
            logger.info(f"Automatically loading trace CSV: {traces_path}")
            self.project_model.set_status_message(
                f"Loading trace data for FOV {fov_idx:03d}..."
            )

            # Load the trace data using the project model
            success = self.project_model.load_processing_csv(
                traces_path,
                self.trace_table_model,
                self.trace_feature_model,
                self.image_model,
            )

            if success:
                self.project_model.set_status_message(
                    f"FOV {fov_idx:03d} ready with trace data"
                )
            else:
                # If automatic loading fails, still mark as ready since images are loaded
                logger.warning(f"Failed to automatically load trace CSV: {traces_path}")
                self.project_model.set_status_message(
                    f"FOV {fov_idx:03d} ready (images only)"
                )
        else:
            self.project_model.set_status_message(
                f"FOV {fov_idx:03d} ready (no trace data)"
            )

        self.project_model.set_is_loading(False)

    def set_trace_panel(self, trace_panel) -> None:
        """Set the trace panel reference for communication."""
        self.trace_panel = trace_panel

    def _on_worker_error(self, message: str) -> None:
        """Handle worker errors."""
        self.project_model.set_is_loading(False)
        self.project_model.set_error_message(message)
        self.project_model.set_status_message("Error loading FOV data")
        self.error_occurred.emit(message)

    def _on_worker_finished(self) -> None:
        """Handle worker completion."""
        self.project_model.set_is_loading(False)

    def _cleanup_worker(self) -> None:
        """Clean up worker resources."""
        if self._worker is not None:
            self._worker.stop()
            self._worker = None


class _VisualizationWorker(QObject):
    """Worker for loading and preprocessing FOV data in background."""

    progress_updated = Signal(str)
    fov_data_loaded = Signal(int, dict, list, dict, dict, Path)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        project_data: dict,
        fov_idx: int,
        selected_channels: list[str],
    ):
        super().__init__()
        self.project_data = project_data
        self.fov_idx = fov_idx
        self.selected_channels = selected_channels

    def process_fov_data(self) -> None:
        """Process FOV data in the background thread."""
        try:
            self.progress_updated.emit(f"Loading data for FOV {self.fov_idx:03d}...")

            if self.fov_idx not in self.project_data["fov_data"]:
                self.error_occurred.emit(
                    f"FOV {self.fov_idx} not found in project data"
                )
                return

            fov_data = self.project_data["fov_data"][self.fov_idx]

            # Use direct channel keys from the selected channels
            image_types = []
            for selected_channel in self.selected_channels:
                if selected_channel in fov_data:
                    image_types.append(selected_channel)

            if not image_types:
                self.error_occurred.emit("No image data found for selected channels")
                return

            image_map: dict[str, np.ndarray] = {}

            # Load and preprocess each image type
            for i, image_type in enumerate(image_types):
                self.progress_updated.emit(
                    f"Loading {image_type} ({i + 1}/{len(image_types)})..."
                )

                image_path = fov_data[image_type]
                if not Path(image_path).exists():
                    logger.warning("Image file not found: %s", image_path)
                    continue

                # Load image data
                image_data = np.load(image_path)

                # Preprocess for visualization
                processed_data = self._preprocess_for_visualization(
                    image_data, image_type
                )
                image_map[image_type] = processed_data

            # Only load image data for fast viewing - trace data loading handled separately
            traces_path = fov_data.get("traces")
            self.fov_data_loaded.emit(
                self.fov_idx,
                image_map,
                [],  # Empty traces for now
                {},  # Empty features for now
                {},  # Empty positions for now
                traces_path,
            )
            self.finished.emit()

        except Exception as e:
            logger.exception("Error processing FOV data")
            self.error_occurred.emit(str(e))

    def _normalize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Normalize a single frame for visualization."""
        frame_float = frame.astype(np.float32)

        max_val = np.max(frame_float)
        if max_val == 0:
            return frame_float

        p1 = np.percentile(frame_float, 1)
        p99 = np.percentile(frame_float, 99)

        if p99 > p1:
            # Apply percentile normalization
            normalized = (frame_float - p1) / (p99 - p1)
            return np.clip(normalized, 0, 1)

        # Fallback for low-contrast images
        return frame_float / max_val

    def _preprocess_for_visualization(
        self, image_data: np.ndarray, data_type: str
    ) -> np.ndarray:
        """Preprocess image data for visualization."""
        if data_type.startswith("seg"):
            # Segmentation data - no preprocessing needed
            return image_data

        # Fluorescence/phase contrast - apply percentile normalization
        if image_data.ndim == 3:  # Time series
            # Normalize each frame independently
            return np.array([self._normalize_frame(frame) for frame in image_data])

        # Single frame
        return self._normalize_frame(image_data)
