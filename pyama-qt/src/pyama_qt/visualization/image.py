"""Image viewer panel for displaying microscopy images and processing results."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from pathlib import Path
from dataclasses import dataclass

import numpy as np
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


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class PositionData:
    """Data structure for cell position information."""

    frames: np.ndarray
    position: dict[str, np.ndarray]  # {"x": array, "y": array}


# =============================================================================
# MAIN IMAGE PANEL
# =============================================================================


class ImagePanel(QWidget):
    """Panel for viewing microscopy images and processing results."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    fovDataLoaded = Signal(
        dict, dict
    )  # image_map, payload with traces_path and seg_labeled
    statusMessage = Signal(str)  # Status messages
    errorMessage = Signal(str)  # Error messages
    loadingStateChanged = Signal(bool)  # Loading state changes
    cell_selected = Signal(str)  # Cell selection events

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initialize_state()
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # STATE INITIALIZATION
    # ------------------------------------------------------------------------
    def _initialize_state(self) -> None:
        """Initialize internal state variables."""
        # Image cache state
        self._image_cache: dict[str, np.ndarray] = {}
        self._current_data_type: str = ""
        self._current_frame_index = 0
        self._max_frame_index = 0

        # Trace and cell state
        self._trace_positions: dict[str, PositionData] = {}
        self._active_trace_id: str | None = None
        self._cell_positions: dict[int, tuple[float, float]] = {}

        # Worker handle
        self._worker: WorkerHandle | None = None

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout."""
        layout = QVBoxLayout(self)

        # Image viewer group
        image_group = QGroupBox("Image Viewer")
        image_layout = QVBoxLayout(image_group)

        # Controls section
        controls_layout = self._build_controls_section()
        image_layout.addLayout(controls_layout)

        # Canvas section
        self.canvas = MplCanvas(self)
        image_layout.addWidget(self.canvas)

        layout.addWidget(image_group)

    def _build_controls_section(self) -> QVBoxLayout:
        """Build the controls section of the UI."""
        controls_layout = QVBoxLayout()

        # Data type selection row
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Data Type:"))
        self.data_type_combo = QComboBox()
        first_row.addWidget(self.data_type_combo)
        controls_layout.addLayout(first_row)

        # Frame navigation row
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

        return controls_layout

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers."""
        # Data type selection
        self.data_type_combo.currentTextChanged.connect(self._on_data_type_selected)

        # Frame navigation
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

        # Canvas interactions
        self.canvas.artist_picked.connect(self._on_artist_picked)

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    def _on_artist_picked(self, artist_id: str):
        """Handle artist picking events from the canvas."""
        if artist_id.startswith("cell_"):
            cell_id = artist_id.split("_")[1]
            self.cell_selected.emit(cell_id)

    def _on_data_type_selected(self, data_type: str):
        """Handle data type selection changes."""
        if data_type and data_type in self._image_cache:
            self._current_data_type = data_type
            self._render_current_frame()

    # ------------------------------------------------------------------------
    # PUBLIC API - SLOTS FOR EXTERNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def on_visualization_requested(
        self, project_data: dict, fov_idx: int, selected_channels: list[str]
    ):
        """Handle visualization requests from other components."""
        # Cancel any existing worker
        if self._worker:
            self._worker.stop()

        # Clear current state
        self.clear_all()

        # Start loading
        self.loadingStateChanged.emit(True)
        self.statusMessage.emit(f"Loading FOV {fov_idx:03d}…")

        # Create and start worker
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
        """Handle trace position updates from trace panel."""
        self._trace_positions = positions
        self._render_current_frame()

    def on_active_trace_changed(self, trace_id: str | None):
        """Handle active trace changes from trace panel."""
        self._active_trace_id = trace_id
        self._render_current_frame()

    # ------------------------------------------------------------------------
    # INTERNAL LOGIC
    # ------------------------------------------------------------------------
    def clear_all(self):
        """Clear all cached data and reset UI state."""
        self._image_cache.clear()
        self._current_data_type = ""
        self.set_current_frame(0)
        self._max_frame_index = 0
        self._update_frame_label()
        self.data_type_combo.clear()
        self.canvas.clear()

    def _on_data_type_selected(self, data_type: str):
        if self._current_data_type == data_type:
            return
        self._current_data_type = data_type
        self._render_current_frame()

    # ------------------------------------------------------------------------
    # FRAME MANAGEMENT
    # ------------------------------------------------------------------------
    def set_current_frame(self, index: int):
        """Set the current frame index with bounds checking."""
        if index < 0:
            index = 0
        elif index > self._max_frame_index:
            index = self._max_frame_index
        self._current_frame_index = index
        self._update_frame_label()
        self._render_current_frame()

    # ------------------------------------------------------------------------
    # RENDERING
    # ------------------------------------------------------------------------
    def _render_current_frame(self):
        """Render the current frame with overlays."""
        image = self._image_cache.get(self._current_data_type)
        if image is None:
            self.canvas.clear()
            return

        # Get the current frame
        frame = image[self._current_frame_index] if image.ndim == 3 else image
        cmap = "viridis" if self._current_data_type.startswith("seg") else "gray"
        self.canvas.plot_image(frame, cmap=cmap, vmin=frame.min(), vmax=frame.max())

        # Add cell position overlays
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

        # Update title
        self.canvas.axes.set_title(
            f"{self._current_data_type} - Frame {self._current_frame_index}"
        )

    def _update_frame_label(self):
        """Update the frame navigation label."""
        self.frame_label.setText(
            f"Frame {self._current_frame_index}/{self._max_frame_index}"
        )

    # ------------------------------------------------------------------------
    # WORKER CALLBACKS
    # ------------------------------------------------------------------------
    def _on_worker_fov_loaded(self, fov_idx: int, image_map: dict, payload: dict):
        """Handle successful FOV data loading from worker."""
        logger.info("FOV %d data loaded with %d image types", fov_idx, len(image_map))

        # Update image cache
        self._image_cache = image_map
        self._max_frame_index = max(
            (arr.shape[0] - 1 for arr in image_map.values() if arr.ndim == 3), default=0
        )

        # Update data type selector
        self.data_type_combo.blockSignals(True)
        self.data_type_combo.clear()
        self.data_type_combo.addItems(image_map.keys())
        self.data_type_combo.blockSignals(False)

        # Select first data type
        if image_map:
            self._on_data_type_selected(next(iter(image_map.keys())))
        self.set_current_frame(0)

        # Update cell positions from segmentation
        seg_labeled = payload.get("seg_labeled")
        if seg_labeled is not None:
            self._update_cell_positions(seg_labeled)

        # Emit signal for other components
        self.fovDataLoaded.emit(image_map, payload)

    def _on_worker_error(self, message: str):
        """Handle worker errors."""
        logger.error("Visualization worker error: %s", message)
        self.errorMessage.emit(message)
        self.loadingStateChanged.emit(False)

    # ------------------------------------------------------------------------
    # HELPER METHODS
    # ------------------------------------------------------------------------
    def _update_cell_positions(self, seg_labeled: np.ndarray):
        """Update cell positions from labeled segmentation data."""
        # This would extract cell positions from the segmentation data
        # Implementation depends on the specific format of seg_labeled
        # For now, this is a placeholder
        pass


# =============================================================================
# BACKGROUND VISUALIZATION WORKER
# =============================================================================


class VisualizationWorker(QObject):
    """Worker for loading and preprocessing FOV data in background."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    progress_updated = Signal(str)  # Progress messages
    fov_data_loaded = Signal(int, dict, object)  # FOV index, image_map, payload
    finished = Signal()  # Worker completion
    error_occurred = Signal(str)  # Error messages

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(
        self, *, project_data: dict, fov_idx: int, selected_channels: list[str]
    ):
        super().__init__()
        self._project_data = project_data
        self._fov_idx = fov_idx
        self._selected_channels = selected_channels

    # ------------------------------------------------------------------------
    # WORK EXECUTION
    # ------------------------------------------------------------------------
    def process_fov_data(self):
        """Process FOV data in background thread."""
        try:
            self.progress_updated.emit(f"Loading data for FOV {self._fov_idx:03d}…")

            # Get FOV data
            fov_data = self._project_data["fov_data"].get(self._fov_idx)
            if not fov_data:
                self.error_occurred.emit(f"FOV {self._fov_idx} not found.")
                return

            # Load selected channels
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

            # Load labeled segmentation if available
            seg_labeled_data = self._load_segmentation(fov_data)

            # Load trace paths for fluorescence channels
            traces_paths = self._get_trace_paths(fov_data)

            # Create payload and emit signal
            payload = {"traces": traces_paths, "seg_labeled": seg_labeled_data}
            self.fov_data_loaded.emit(self._fov_idx, image_map, payload)

        except Exception as e:
            logger.exception("Error processing FOV data")
            self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()

    # ------------------------------------------------------------------------
    # DATA LOADING HELPERS
    # ------------------------------------------------------------------------
    def _load_segmentation(self, fov_data: dict) -> np.ndarray | None:
        """Load labeled segmentation data if available."""
        if "segmentation_labeled" not in fov_data:
            return None

        try:
            seg_path = Path(fov_data["segmentation_labeled"])
            if seg_path.exists():
                # Load the first frame of the labeled segmentation
                return np.load(seg_path, mmap_mode="r")[0]
        except Exception as e:
            logger.error(f"Failed to load segmentation_labeled: {e}")
        return None

    def _get_trace_paths(self, fov_data: dict) -> dict[str, Path]:
        """Get trace file paths for fluorescence channels."""
        traces_paths = {}
        for channel_name in self._selected_channels:
            if channel_name.startswith("fl_ch_"):
                channel_idx = channel_name.split("_")[-1]
                trace_key = f"traces_ch_{channel_idx}"
                if trace_key in fov_data:
                    traces_paths[channel_idx] = Path(fov_data[trace_key])
        return traces_paths

    # ------------------------------------------------------------------------
    # IMAGE PROCESSING
    # ------------------------------------------------------------------------
    def _preprocess(self, data: np.ndarray, dtype: str) -> np.ndarray:
        """Preprocess image data based on data type."""
        if dtype.startswith("seg"):
            return data.astype(np.uint8)
        if data.ndim == 3:
            return np.stack([self._normalize(f) for f in data])
        return self._normalize(data)

    def _normalize(self, frame: np.ndarray) -> np.ndarray:
        """Normalize frame to uint8 range using percentile stretching."""
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
