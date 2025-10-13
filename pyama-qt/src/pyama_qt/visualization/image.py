"""Image viewer panel for displaying microscopy images and processing results."""

import logging
from pathlib import Path

import numpy as np
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_qt.services import WorkerHandle, start_worker

from ..components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


@dataclass
class PositionData:
    """Data structure for cell position information."""

    frames: np.ndarray
    position: dict[str, np.ndarray]  # {"x": array, "y": array}


class ImagePanel(QWidget):
    """Panel for viewing microscopy images and processing results."""

    # Signals for other components
    fovDataLoaded = Signal(
        dict, dict
    )  # image_map, payload with traces_path and seg_labeled
    statusMessage = Signal(str)
    errorMessage = Signal(str)
    loadingStateChanged = Signal(bool)
    cell_selected = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.build()
        self.bind()
        # --- State from ImageCacheModel ---
        self._image_cache: dict[str, np.ndarray] = {}
        self._current_data_type: str = ""
        self._current_frame_index = 0
        self._max_frame_index = 0
        self._trace_positions: dict[str, PositionData] = {}
        self._active_trace_id: str | None = None
        self._cell_positions: dict[int, tuple[float, float]] = {}

        # --- Worker ---
        self._worker: WorkerHandle | None = None

    def build(self) -> None:
        layout = QVBoxLayout(self)
        image_group = QGroupBox("Image Viewer")
        image_layout = QVBoxLayout(image_group)
        controls_layout = QVBoxLayout()
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Data Type:"))
        first_row.addStretch()
        self.data_type_combo = QComboBox()
        first_row.addWidget(self.data_type_combo)
        controls_layout.addLayout(first_row)
        second_row = QHBoxLayout()
        self.prev_frame_10_button = QPushButton("<<")
        second_row.addWidget(self.prev_frame_10_button)
        self.prev_frame_button = QPushButton("<")
        second_row.addWidget(self.prev_frame_button)
        self.frame_label = QLabel("Frame 0/0")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        second_row.addWidget(self.frame_label)
        self.next_frame_button = QPushButton(">")
        second_row.addWidget(self.next_frame_button)
        self.next_frame_10_button = QPushButton(">>")
        second_row.addWidget(self.next_frame_10_button)
        controls_layout.addLayout(second_row)
        image_layout.addLayout(controls_layout)
        self.canvas = MplCanvas(self)
        image_layout.addWidget(self.canvas)
        layout.addWidget(image_group)

    def bind(self) -> None:
        self.data_type_combo.currentTextChanged.connect(self._on_data_type_selected)
        self.prev_frame_button.clicked.connect(
            lambda: self.set_current_frame(self._current_frame_index - 1)
        )
        self.next_frame_button.clicked.connect(
            lambda: self.set_current_frame(self._current_frame_index + 1)
        )
        self.prev_frame_10_button.clicked.connect(
            lambda: self.set_current_frame(self._current_frame_index - 10)
        )
        self.next_frame_10_button.clicked.connect(
            lambda: self.set_current_frame(self._current_frame_index + 10)
        )
        self.canvas.artist_picked.connect(self._on_artist_picked)

    def _on_artist_picked(self, artist_id: str):
        if artist_id.startswith("cell_"):
            cell_id = artist_id.split("_")[1]
            self.cell_selected.emit(cell_id)

    # --- Public Slots for connection to other components ---
    def on_visualization_requested(
        self, project_data: dict, fov_idx: int, selected_channels: list[str]
    ):
        if self._worker:
            self._worker.stop()
        self.clear_all()
        self.loadingStateChanged.emit(True)
        self.statusMessage.emit(f"Loading FOV {fov_idx:03d}…")

        worker = VisualizationWorker(
            project_data=project_data,
            fov_idx=fov_idx,
            selected_channels=selected_channels,
        )
        worker.progress_updated.connect(self.statusMessage.emit)
        worker.fov_data_loaded.connect(self._on_worker_fov_loaded)
        worker.error_occurred.connect(self._on_worker_error)
        worker.finished.connect(lambda: self.loadingStateChanged.emit(False))

        self._worker = start_worker(
            worker,
            start_method="process_fov_data",
            finished_callback=lambda: setattr(self, "_worker", None),
        )

    def on_trace_positions_changed(self, positions: dict):
        self._trace_positions = positions
        self._render_current_frame()

    def on_active_trace_changed(self, trace_id: str | None):
        self._active_trace_id = trace_id
        self._render_current_frame()

    # --- Internal Logic ---
    def clear_all(self):
        self._image_cache.clear()
        self._current_data_type = ""
        self.set_current_frame(0)
        self._max_frame_index = 0
        self._update_frame_label()
        self.data_type_combo.clear()
        self.canvas.clear()

    def set_current_frame(self, index: int):
        index = max(0, min(index, self._max_frame_index))
        if index == self._current_frame_index:
            return
        self._current_frame_index = index
        self._update_frame_label()
        self._render_current_frame()

    def _on_data_type_selected(self, data_type: str):
        if self._current_data_type == data_type:
            return
        self._current_data_type = data_type
        self._render_current_frame()

    def _render_current_frame(self):
        image = self._image_cache.get(self._current_data_type)
        if image is None:
            self.canvas.clear()
            return
        frame = image[self._current_frame_index] if image.ndim == 3 else image
        cmap = "viridis" if self._current_data_type.startswith("seg") else "gray"
        self.canvas.plot_image(frame, cmap=cmap, vmin=frame.min(), vmax=frame.max())

        self.canvas.clear_overlays()
        for cell_id, (x, y) in self._cell_positions.items():
            is_active = str(cell_id) == self._active_trace_id
            color = "red" if is_active else "gray"
            radius = 10 if is_active else 5
            self.canvas.plot_overlay(
                f"cell_{cell_id}",
                {
                    "type": "circle",
                    "xy": (x, y),
                    "radius": radius,
                    "edgecolor": color,
                    "facecolor": "none",
                },
            )

        self.canvas.axes.set_title(
            f"{self._current_data_type} - Frame {self._current_frame_index}"
        )

    def _update_frame_label(self):
        self.frame_label.setText(
            f"Frame {self._current_frame_index}/{self._max_frame_index}"
        )

    # --- Worker Callbacks ---
    def _on_worker_fov_loaded(self, fov_idx: int, image_map: dict, payload: dict):
        logger.info("FOV %d data loaded with %d image types", fov_idx, len(image_map))
        self._image_cache = image_map
        self._max_frame_index = max(
            (arr.shape[0] - 1 for arr in image_map.values() if arr.ndim == 3), default=0
        )
        self.data_type_combo.blockSignals(True)
        self.data_type_combo.clear()
        self.data_type_combo.addItems(image_map.keys())
        self.data_type_combo.blockSignals(False)
        if image_map:
            self._on_data_type_selected(next(iter(image_map.keys())))
        self.set_current_frame(0)

        seg_labeled = payload.get("seg_labeled")
        if seg_labeled is not None:
            self._update_cell_positions(seg_labeled)

        self.fovDataLoaded.emit(image_map, payload)

    def _on_worker_error(self, message: str):
        logger.error("Visualization worker error: %s", message)
        self.errorMessage.emit(message)
        self.loadingStateChanged.emit(False)


class VisualizationWorker(QObject):
    """Worker for loading and preprocessing FOV data in background."""

    progress_updated = Signal(str)
    fov_data_loaded = Signal(int, dict, object)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(
        self, *, project_data: dict, fov_idx: int, selected_channels: list[str]
    ):
        super().__init__()
        self._project_data = project_data
        self._fov_idx = fov_idx
        self._selected_channels = selected_channels

    def process_fov_data(self):
        try:
            self.progress_updated.emit(f"Loading data for FOV {self._fov_idx:03d}…")
            fov_data = self._project_data["fov_data"].get(self._fov_idx)
            if not fov_data:
                self.error_occurred.emit(f"FOV {self._fov_idx} not found.")
                return

            image_map = {}
            for i, channel in enumerate(self._selected_channels, 1):
                self.progress_updated.emit(
                    f"Loading {channel} ({i}/{len(self._selected_channels)})…"
                )
                path = Path(fov_data[channel])
                if path.exists():
                    image_data = np.load(path)
                    image_map[channel] = self._preprocess(image_data, channel)

            if not image_map:
                self.error_occurred.emit("No image data found for selected channels.")
                return

            # Also load labeled segmentation if available
            seg_labeled_data = None
            if "segmentation_labeled" in fov_data:
                try:
                    seg_path = Path(fov_data["segmentation_labeled"])
                    if seg_path.exists():
                        # Load the first frame of the labeled segmentation
                        seg_labeled_data = np.load(seg_path, mmap_mode="r")[0]
                except Exception as e:
                    logger.error(f"Failed to load segmentation_labeled: {e}")

            traces_paths = {}
            for channel_name in self._selected_channels:
                if channel_name.startswith("fl_ch_"):
                    channel_idx = channel_name.split("_")[-1]
                    trace_key = f"traces_ch_{channel_idx}"
                    if trace_key in fov_data:
                        traces_paths[channel_idx] = Path(fov_data[trace_key])

            payload = {"traces": traces_paths, "seg_labeled": seg_labeled_data}
            self.fov_data_loaded.emit(self._fov_idx, image_map, payload)
        except Exception as e:
            logger.exception("Error processing FOV data")
            self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()

    def _preprocess(self, data: np.ndarray, dtype: str) -> np.ndarray:
        if dtype.startswith("seg"):
            return data.astype(np.uint8)
        if data.ndim == 3:
            return np.stack([self._normalize(f) for f in data])
        return self._normalize(data)

    def _normalize(self, frame: np.ndarray) -> np.ndarray:
        if frame.dtype == np.uint8:
            return frame
        f = frame.astype(np.float32)
        p1, p99 = np.percentile(f, 1), np.percentile(f, 99)
        if p99 <= p1:
            p1, p99 = f.min(), f.max()
        if p99 <= p1:
            return np.zeros_like(f, dtype=np.uint8)
        norm = np.clip((f - p1) / (p99 - p1), 0, 1)
        return (norm * 255).astype(np.uint8)
