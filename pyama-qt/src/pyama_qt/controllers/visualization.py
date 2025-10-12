"""Controller coordinating visualization data loading and display."""

import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal

from pyama_core.io.results_yaml import discover_processing_results

from pyama_qt.models.visualization import (
    FeatureData,
    ImageCacheModel,
    ProjectModel,
    TraceFeatureModel,
    TraceSelectionModel,
    TraceTableModel,
)
from pyama_qt.services import WorkerHandle, start_worker
from pyama_qt.views.visualization.page import VisualizationPage

logger = logging.getLogger(__name__)


class VisualizationController(QObject):
    """Controller implementing strict MVC rules for the visualization tab."""

    def __init__(self, view: VisualizationPage) -> None:
        super().__init__()
        self._view = view
        self._project_model = ProjectModel()
        self._image_model = ImageCacheModel()
        self._trace_table_model = TraceTableModel()
        self._trace_feature_model = TraceFeatureModel()
        self._trace_selection_model = TraceSelectionModel()
        self._worker: WorkerHandle | None = None
        self._processing_status_model = None

        self._project_data: dict | None = None
        self._current_frame_index: int = 0
        self._current_data_type: str = ""
        self._trace_features: dict[str, FeatureData] = {}
        self._trace_good_status: dict[str, bool] = {}
        self._trace_source_path: Path | None = None

        self._connect_view_signals()
        self._connect_model_signals()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        self._view.project_panel.project_load_requested.connect(
            self._on_project_load_requested
        )
        self._view.project_panel.visualization_requested.connect(
            self._on_visualization_requested
        )
        self._view.image_panel.data_type_selected.connect(self._on_data_type_selected)
        self._view.image_panel.frame_delta_requested.connect(
            self._on_frame_delta_requested
        )
        self._view.trace_panel.active_trace_changed.connect(
            self._on_active_trace_selected
        )
        self._view.trace_panel.good_state_changed.connect(self._on_good_state_changed)
        self._view.trace_panel.save_requested.connect(self._on_save_requested)

    def _connect_model_signals(self) -> None:
        self._project_model.projectDataChanged.connect(self._handle_project_data)
        self._project_model.availableChannelsChanged.connect(
            self._handle_available_channels
        )
        self._project_model.statusMessageChanged.connect(self._handle_status_message)
        self._project_model.errorMessageChanged.connect(self._handle_error_message)
        self._project_model.isLoadingChanged.connect(self._handle_loading_state)

        self._image_model.cacheReset.connect(self._handle_image_cache_reset)
        self._image_model.currentDataTypeChanged.connect(
            self._handle_current_data_type_changed
        )
        self._image_model.frameBoundsChanged.connect(self._handle_frame_bounds_changed)
        self._image_model.currentFrameChanged.connect(self._handle_frame_changed)
        self._image_model.tracePositionsChanged.connect(
            self._handle_trace_positions_changed
        )
        self._image_model.activeTraceChanged.connect(
            self._handle_image_active_trace_changed
        )

        self._trace_table_model.tracesReset.connect(self._handle_traces_reset)
        self._trace_table_model.goodStateChanged.connect(
            self._handle_good_state_changed_from_model
        )

        self._trace_feature_model.featureDataChanged.connect(
            self._handle_feature_data_changed
        )
        self._trace_feature_model.availableFeaturesChanged.connect(
            self._handle_feature_list_changed
        )

        self._trace_selection_model.activeTraceChanged.connect(
            self._handle_selection_change
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_processing_status_model(self, status_model) -> None:
        """Set the processing status model to prevent conflicts."""
        self._processing_status_model = status_model

        # Connect to processing status changes to update UI
        if hasattr(status_model, 'isProcessingChanged'):
            status_model.isProcessingChanged.connect(self._on_processing_status_changed)

    def _on_processing_status_changed(self, is_processing: bool) -> None:
        """Handle processing status changes to update visualization UI."""
        if is_processing:
            # Disable visualization controls during processing
            self._view.project_panel.set_visualize_enabled(False)
            self._view.project_panel.set_visualize_button_text("Processing Active")
        else:
            # Re-enable visualization controls when processing completes
            self._view.project_panel.set_visualize_enabled(True)
            self._view.project_panel.set_visualize_button_text("Start Visualization")

    # ------------------------------------------------------------------
    # View → Controller handlers
    # ------------------------------------------------------------------
    def _on_project_load_requested(self, project_path: Path) -> None:
        logger.info("Loading project from %s", project_path)
        self._project_model.set_is_loading(True)
        self._project_model.set_error_message("")
        self._project_model.set_status_message(f"Loading project: {project_path.name}")
        try:
            project_results = discover_processing_results(project_path)
            project_data = project_results.to_dict()
            self._project_data = project_data
            self._project_model.set_project_path(project_path)
            self._project_model.set_project_data(project_data)
            channels = self._extract_available_channels(project_data)
            self._project_model.set_available_channels(channels)
            self._project_model.set_status_message(
                self._format_project_status(project_data)
            )
        except Exception as exc:
            message = self._format_project_error(project_path, exc)
            logger.exception("Failed to load project")
            self._project_model.set_error_message(message)
            self._view.status_bar.showMessage(message)
        finally:
            self._project_model.set_is_loading(False)

    def _on_visualization_requested(
        self, fov_idx: int, selected_channels: list[str]
    ) -> None:
        # Prevent visualization during active processing
        if self._processing_status_model and self._processing_status_model.is_processing():
            logger.warning("Cannot start visualization while processing is active")
            self._view.project_panel.set_visualize_button_text("Processing Active")
            return

        if not self._project_data:
            self._view.status_bar.showMessage("Load a project before visualizing")
            return
        self._cancel_worker()
        self._clear_trace_data()
        self._image_model.remove_images()
        self._project_model.set_is_loading(True)
        self._project_model.set_status_message(f"Loading FOV {fov_idx:03d}…")
        self._view.project_panel.set_visualize_button_text("Loading...")

        worker = _VisualizationWorker(
            project_data=self._project_data,
            fov_idx=fov_idx,
            selected_channels=selected_channels,
        )
        worker.progress_updated.connect(self._handle_worker_progress)
        worker.fov_data_loaded.connect(self._handle_worker_fov_loaded)
        worker.error_occurred.connect(self._handle_worker_error)
        worker.finished.connect(self._handle_worker_finished)

        self._worker = start_worker(
            worker,
            start_method="process_fov_data",
            finished_callback=self._cleanup_worker,
        )

    def _on_data_type_selected(self, data_type: str) -> None:
        self._image_model.set_current_data_type(data_type)

    def _on_frame_delta_requested(self, delta: int) -> None:
        self._image_model.set_current_frame(self._current_frame_index + delta)

    def _on_active_trace_selected(self, trace_id: str) -> None:
        self._trace_selection_model.set_active_trace(trace_id)
        self._image_model.set_active_trace(trace_id)

    def _on_good_state_changed(self, trace_id: str, is_good: bool) -> None:
        self._trace_table_model.set_good_state(trace_id, is_good)

    def _on_save_requested(
        self, good_map: dict[str, bool], target: Path | None
    ) -> None:
        if target is None:
            logger.warning("Save requested without a target path")
            return
        for trace_id, state in good_map.items():
            self._trace_table_model.set_good_state(trace_id, state)
        success = self._trace_table_model.save_inspected_data(target)
        message = (
            f"Saved inspected data to {target.name}"
            if success
            else "Failed to save inspected data"
        )
        self._view.status_bar.showMessage(message)

    # ------------------------------------------------------------------
    # Model → Controller handlers
    # ------------------------------------------------------------------
    def _handle_project_data(self, project_data: dict) -> None:
        if project_data:
            self._view.project_panel.set_project_details(project_data)

    def _handle_available_channels(self, channels: list[str]) -> None:
        self._view.project_panel.set_available_channels(channels)
        self._view.project_panel.reset_channel_selection()

    def _handle_status_message(self, message: str) -> None:
        self._view.project_panel.set_status_message(message)
        if message:
            self._view.status_bar.showMessage(message)

    def _handle_error_message(self, message: str) -> None:
        if message:
            self._view.status_bar.showMessage(message)

    def _handle_loading_state(self, is_loading: bool) -> None:
        self._view.project_panel.set_loading(is_loading)
        if not is_loading:
            self._view.project_panel.set_visualize_button_text("Start Visualization")

    def _handle_image_cache_reset(self) -> None:
        types = self._image_model.available_types()
        current = self._image_model.current_data_type()
        self._view.image_panel.set_available_data_types(types, current)
        self._render_current_frame()

    def _handle_current_data_type_changed(self, data_type: str) -> None:
        self._current_data_type = data_type or ""
        if data_type:
            self._view.image_panel.set_current_data_type(data_type)
        self._render_current_frame()

    def _handle_frame_bounds_changed(self, current: int, maximum: int) -> None:
        self._current_frame_index = current
        self._view.image_panel.set_frame_info(current, maximum)

    def _handle_frame_changed(self, frame: int) -> None:
        self._current_frame_index = frame
        self._view.image_panel.set_frame_info(
            frame, self._image_model.frame_bounds()[1]
        )
        self._render_current_frame()

    def _handle_trace_positions_changed(self, positions: dict) -> None:
        self._view.image_panel.set_trace_positions(positions)
        self._render_current_frame()

    def _handle_image_active_trace_changed(self, trace_id: str | None) -> None:
        self._view.image_panel.set_active_trace(trace_id)
        self._render_current_frame()

    def _handle_traces_reset(self) -> None:
        records = self._trace_table_model.traces()
        self._trace_good_status = {
            str(record.cell_id): record.good for record in records
        }
        self._refresh_trace_panel()

    def _handle_good_state_changed_from_model(
        self, trace_id: str, is_good: bool
    ) -> None:
        self._trace_good_status[trace_id] = is_good
        self._view.trace_panel.update_good_state(trace_id, is_good)

    def _handle_feature_data_changed(self, data: dict[str, FeatureData]) -> None:
        self._trace_features = dict(data)
        self._refresh_trace_panel()

    def _handle_feature_list_changed(self, features: list[str]) -> None:
        # The trace panel dataset refresh will handle updating dropdown with new features.
        if features:
            self._refresh_trace_panel()

    def _handle_selection_change(self, trace_id: str | None) -> None:
        self._view.trace_panel.set_active_trace(trace_id)
        self._view.image_panel.set_active_trace(trace_id)

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------
    def _handle_worker_progress(self, message: str) -> None:
        self._project_model.set_status_message(message)

    def _handle_worker_fov_loaded(
        self,
        fov_idx: int,
        image_map: dict[str, np.ndarray],
        traces_path: Path | None,
    ) -> None:
        logger.info("FOV %s data loaded (%d image types)", fov_idx, len(image_map))
        self._image_model.set_images(image_map)
        self._trace_source_path = traces_path

        if traces_path and traces_path.exists():
            self._project_model.set_status_message(
                f"Loading trace data for FOV {fov_idx:03d}..."
            )
            success = self._project_model.load_processing_csv(
                traces_path,
                self._trace_table_model,
                self._trace_feature_model,
                self._image_model,
            )
            if success:
                self._project_model.set_status_message(
                    f"FOV {fov_idx:03d} ready with trace data"
                )
            else:
                self._trace_source_path = None
                self._project_model.set_status_message(
                    f"FOV {fov_idx:03d} ready (images only)"
                )
        else:
            self._trace_source_path = None
            self._project_model.set_status_message(
                f"FOV {fov_idx:03d} ready (no trace data)"
            )

        self._project_model.set_is_loading(False)

    def _handle_worker_error(self, message: str) -> None:
        logger.error("Visualization worker error: %s", message)
        self._project_model.set_is_loading(False)
        self._project_model.set_error_message(message)

    def _handle_worker_finished(self) -> None:
        self._project_model.set_is_loading(False)

    def _cleanup_worker(self) -> None:
        self._worker = None
        self._view.project_panel.set_visualize_button_text("Start Visualization")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _cancel_worker(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker = None

    def _render_current_frame(self) -> None:
        image = self._image_model.image_for_current_type()
        if image is None:
            return
        frame = image
        if image.ndim == 3:
            index = max(0, min(self._current_frame_index, image.shape[0] - 1))
            frame = image[index]
        self._view.image_panel.render_image(frame, data_type=self._current_data_type)

    def _refresh_trace_panel(self) -> None:
        if not self._trace_features:
            self._view.trace_panel.clear()
            return

        features = self._trace_feature_model.available_features()
        self._view.trace_panel.set_trace_dataset(
            traces=self._trace_features,
            good_status=self._trace_good_status,
            features=features,
            source_path=self._trace_source_path,
        )
        self._view.trace_panel.set_active_trace(
            self._trace_selection_model.active_trace()
        )

    def _clear_trace_data(self) -> None:
        self._trace_features.clear()
        self._trace_good_status.clear()
        self._trace_source_path = None
        self._view.trace_panel.clear()

    @staticmethod
    def _extract_available_channels(project_data: dict) -> list[str]:
        if not project_data.get("fov_data"):
            return []
        first_fov = next(iter(project_data["fov_data"].values()))
        channels = list(first_fov.keys())
        if "traces" in channels:
            channels.remove("traces")
        return sorted(channels)

    @staticmethod
    def _format_project_status(project_data: dict) -> str:
        has_project_file = project_data.get("has_project_file", False)
        status = project_data.get("processing_status", "unknown")
        n_fov = project_data.get("n_fov", 0)
        if has_project_file:
            status_msg = f"Project loaded: {n_fov} FOVs, Status: {status.title()}"
            if status != "completed":
                status_msg += " ⚠"
            return status_msg
        return f"Project loaded: {n_fov} FOVs"

    @staticmethod
    def _format_project_error(project_path: Path, exc: Exception) -> str:
        message = str(exc)
        if "No FOV directories found" in message:
            return (
                f"No data found in {project_path}.\n"
                "Ensure the directory contains FOV subdirectories."
            )
        return message


class _VisualizationWorker(QObject):
    """Worker for loading and preprocessing FOV data in background."""

    progress_updated = Signal(str)
    fov_data_loaded = Signal(int, dict, object)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        *,
        project_data: dict,
        fov_idx: int,
        selected_channels: list[str],
    ) -> None:
        super().__init__()
        self._project_data = project_data
        self._fov_idx = fov_idx
        self._selected_channels = selected_channels

    def process_fov_data(self) -> None:
        try:
            self.progress_updated.emit(f"Loading data for FOV {self._fov_idx:03d}…")
            if self._fov_idx not in self._project_data["fov_data"]:
                self.error_occurred.emit(
                    f"FOV {self._fov_idx} not found in project data"
                )
                return

            fov_data = self._project_data["fov_data"][self._fov_idx]
            image_types = [
                channel for channel in self._selected_channels if channel in fov_data
            ]

            if not image_types:
                self.error_occurred.emit("No image data found for selected channels")
                return

            image_map: dict[str, np.ndarray] = {}

            for idx, image_type in enumerate(image_types, start=1):
                self.progress_updated.emit(
                    f"Loading {image_type} ({idx}/{len(image_types)})…"
                )
                image_path = Path(fov_data[image_type])
                if not image_path.exists():
                    logger.warning("Image file not found: %s", image_path)
                    continue
                image_data = np.load(image_path)
                processed = self._preprocess_for_visualization(image_data, image_type)
                image_map[image_type] = processed

            traces_value = fov_data.get("traces")
            traces_path = Path(traces_value) if traces_value else None
            self.fov_data_loaded.emit(self._fov_idx, image_map, traces_path)
            self.finished.emit()
        except Exception as exc:
            logger.exception("Error processing FOV data")
            self.error_occurred.emit(str(exc))

    def _preprocess_for_visualization(
        self, image_data: np.ndarray, data_type: str
    ) -> np.ndarray:
        if data_type.startswith("seg"):
            return image_data.astype(np.uint8, copy=False)

        if image_data.ndim == 3:
            frames = [self._normalize_frame(frame) for frame in image_data]
            return np.stack(frames, axis=0)
        return self._normalize_frame(image_data)

    def _normalize_frame(self, frame: np.ndarray) -> np.ndarray:
        if frame.dtype == np.uint8:
            return frame
        frame_float = frame.astype(np.float32)
        max_val = np.max(frame_float)
        if max_val <= 0:
            return np.zeros_like(frame, dtype=np.uint8)
        p1 = np.percentile(frame_float, 1)
        p99 = np.percentile(frame_float, 99)
        if p99 > p1:
            normalized = (frame_float - p1) / (p99 - p1)
            normalized = np.clip(normalized, 0, 1)
            return (normalized * 255).astype(np.uint8)
        normalized = frame_float / max_val
        normalized = np.clip(normalized, 0, 1)
        return (normalized * 255).astype(np.uint8)
