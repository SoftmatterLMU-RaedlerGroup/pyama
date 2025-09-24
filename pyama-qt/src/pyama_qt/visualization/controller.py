"""Controller coordinating visualization data loading and display."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal

from pyama_core.io.results_yaml import discover_processing_results
from pyama_core.io.processing_csv import parse_trace_data

from pyama_qt.visualization.state import (
    VisualizationState,
    ProjectLoadRequest,
    VisualizationRequest,
    TraceSelectionRequest,
    FrameNavigationRequest,
    DataTypeChangeRequest,
)
from pyama_qt.services import WorkerHandle, start_worker

logger = logging.getLogger(__name__)


class VisualizationController(QObject):
    """Encapsulates visualization data loading and state management."""

    state_changed = Signal(object)
    project_loaded = Signal(dict)
    fov_data_ready = Signal(int)
    trace_data_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._state = VisualizationState()
        self._worker: WorkerHandle | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def current_state(self) -> VisualizationState:
        return self._state

    def load_project(self, request: ProjectLoadRequest) -> None:
        """Load a PyAMA-Qt processing results project."""
        logger.info("Loading project from %s", request.project_path)

        try:
            self._update_state(
                status_message=f"Loading project: {request.project_path.name}",
                error_message="",
                is_loading=True,
            )

            # Discover processing results
            project_data = discover_processing_results(request.project_path)

            # Extract available channels from first FOV
            available_channels = self._extract_available_channels(project_data)

            self._update_state(
                project_path=request.project_path,
                project_data=project_data,
                available_channels=available_channels,
                is_loading=False,
                status_message=self._format_project_status(project_data),
                error_message="",
            )

            self.project_loaded.emit(project_data)

        except Exception as e:
            error_msg = str(e)
            if "No FOV directories found" in error_msg:
                error_msg = f"No data found in {request.project_path}\n\nMake sure you've selected a directory containing FOV subdirectories (fov_0000, fov_0001, etc.)"

            self._update_state(
                is_loading=False,
                error_message=error_msg,
                status_message="Error loading project",
            )
            self.error_occurred.emit(error_msg)

    def start_visualization(self, request: VisualizationRequest) -> None:
        """Start visualization for a specific FOV."""
        if self._state.project_data is None:
            self.error_occurred.emit("No project loaded")
            return

        if self._worker is not None:
            logger.warning("Visualization already running; canceling previous")
            self._cleanup_worker()

        logger.info(
            "Starting visualization for FOV %d with channels %s",
            request.fov_idx,
            request.selected_channels,
        )

        # Clear image cache for new FOV
        self._state.image_cache.clear()

        self._update_state(
            current_fov=request.fov_idx,
            selected_channels=request.selected_channels,
            current_frame_index=0,
            is_loading=True,
            status_message=f"Loading FOV {request.fov_idx:03d}...",
        )

        # Start background worker
        worker = _VisualizationWorker(
            project_data=self._state.project_data,
            fov_idx=request.fov_idx,
            selected_channels=request.selected_channels,
            image_cache=self._state.image_cache,
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
        self._update_state(active_trace_id=request.trace_id)

    def navigate_frame(self, request: FrameNavigationRequest) -> None:
        """Navigate to a specific frame."""
        if 0 <= request.frame_index <= self._state.max_frame_index:
            self._update_state(current_frame_index=request.frame_index)

    def change_data_type(self, request: DataTypeChangeRequest) -> None:
        """Change the displayed data type."""
        self._update_state(current_data_type=request.data_type)

    def cancel_loading(self) -> None:
        """Cancel any ongoing loading operation."""
        if self._worker is not None:
            self._cleanup_worker()
            self._update_state(is_loading=False, status_message="Loading canceled")

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------
    def _extract_available_channels(self, project_data: dict) -> list[str]:
        """Extract available channels from project data."""
        if not project_data.get("fov_data"):
            return []

        # Get first FOV to determine available channels
        first_fov_data = next(iter(project_data["fov_data"].values()))
        channels = []

        # Check for phase contrast
        if any(k.startswith("pc_ch_") for k in first_fov_data.keys()):
            channels.append("pc")

        # Check for fluorescence channels
        fl_channels = set()
        for key in first_fov_data.keys():
            if key.startswith("fl_ch_") or key.startswith("fl_corrected_ch_"):
                # Extract channel number
                parts = key.split("_")
                if len(parts) >= 3:
                    try:
                        ch_num = int(parts[-1])
                        fl_channels.add(f"fl_{ch_num}")
                    except ValueError:
                        continue

        channels.extend(sorted(fl_channels))
        return channels

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

    def _on_worker_progress(self, message: str) -> None:
        """Handle progress updates from worker."""
        self._update_state(status_message=message)

    def _on_fov_data_loaded(self, fov_idx: int) -> None:
        """Handle FOV data loaded notification."""
        # Update max frame index based on loaded data
        if self._state.image_cache:
            first_data = next(iter(self._state.image_cache.values()))
            if hasattr(first_data, "shape") and len(first_data.shape) >= 3:
                max_frames = first_data.shape[0] - 1
                self._update_state(max_frame_index=max_frames)

        self._update_state(is_loading=False)
        self.fov_data_ready.emit(fov_idx)

        # Load trace data for this FOV
        self._load_trace_data(fov_idx)

    def _on_worker_error(self, message: str) -> None:
        """Handle worker errors."""
        self._update_state(
            is_loading=False,
            error_message=message,
            status_message="Error loading FOV data",
        )
        self.error_occurred.emit(message)

    def _on_worker_finished(self) -> None:
        """Handle worker completion."""
        self._update_state(is_loading=False)

    def _load_trace_data(self, fov_idx: int) -> None:
        """Load trace data for the specified FOV."""
        try:
            if self._state.project_data is None:
                return

            fov_catalog = self._state.project_data.get("fov_data", {})
            fov_entry = fov_catalog.get(fov_idx, {})
            traces_path = fov_entry.get("traces")

            if traces_path is None:
                # No traces for this FOV
                self._update_state(
                    trace_positions={},
                    active_trace_id=None,
                    trace_data={},
                    traces_csv_path=None,
                )
                self.trace_data_ready.emit({})
                return

            # Parse the trace data
            trace_data = parse_trace_data(traces_path)

            if not trace_data["cell_ids"]:
                # No valid data found
                self._update_state(
                    trace_positions={},
                    active_trace_id=None,
                    trace_data={},
                    traces_csv_path=traces_path,
                )
                self.trace_data_ready.emit({})
                return

            # Convert positions to string keys for consistency
            positions_with_string_keys = {
                str(k): v for k, v in trace_data["positions"].items()
            }

            self._update_state(
                trace_positions=positions_with_string_keys,
                active_trace_id=None,
                trace_data=trace_data,
                traces_csv_path=traces_path,
            )

            self.trace_data_ready.emit(trace_data)

        except Exception:
            logger.exception("Error loading trace data for FOV %d", fov_idx)
            # Keep UI stable on trace loading errors
            self._update_state(
                trace_positions={},
                active_trace_id=None,
                trace_data={},
                traces_csv_path=None,
            )
            self.trace_data_ready.emit({})

    def _cleanup_worker(self) -> None:
        """Clean up worker resources."""
        if self._worker is not None:
            self._worker.stop()
            self._worker = None

    def _update_state(self, **updates) -> None:
        """Update state and emit change signal."""
        for key, value in updates.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)
        self.state_changed.emit(self._state)


class _VisualizationWorker(QObject):
    """Worker for loading and preprocessing FOV data in background."""

    progress_updated = Signal(str)
    fov_data_loaded = Signal(int)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        project_data: dict,
        fov_idx: int,
        selected_channels: list[str],
        image_cache: dict,
    ):
        super().__init__()
        self.project_data = project_data
        self.fov_idx = fov_idx
        self.selected_channels = selected_channels
        self.image_cache = image_cache

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

            # Clear image cache
            self.image_cache.clear()

            # Filter image types based on selected channels
            image_types = []
            for selected_channel in self.selected_channels:
                if selected_channel == "pc":
                    # Add phase contrast channels
                    pc_types = [k for k in fov_data.keys() if k.startswith("pc_ch_")]
                    image_types.extend(pc_types)
                elif selected_channel.startswith("fl_"):
                    # Extract channel number
                    channel_num = selected_channel.split("_")[1]
                    # Prefer corrected over uncorrected
                    corrected_key = f"fl_corrected_ch_{channel_num}"
                    uncorrected_key = f"fl_ch_{channel_num}"

                    if corrected_key in fov_data:
                        image_types.append(corrected_key)
                    elif uncorrected_key in fov_data:
                        image_types.append(uncorrected_key)

            # Also include segmentation data if available
            seg_types = [k for k in fov_data.keys() if k.startswith("seg")]
            image_types.extend(seg_types)

            if not image_types:
                self.error_occurred.emit("No image data found for selected channels")
                return

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
                self.image_cache[image_type] = processed_data

            self.fov_data_loaded.emit(self.fov_idx)
            self.finished.emit()

        except Exception as e:
            logger.exception("Error processing FOV data")
            self.error_occurred.emit(str(e))

    def _normalize_frame(frame: np.ndarray) -> np.ndarray:
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
