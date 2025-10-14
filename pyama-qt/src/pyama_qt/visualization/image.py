"""Image viewer panel for displaying microscopy images and processing results."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot, Qt
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
from pyama_qt.types.visualization import PositionData
from pyama_qt.components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN IMAGE PANEL
# =============================================================================


class ImagePanel(QWidget):
    """Panel for viewing microscopy images and processing results."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    fov_data_loaded = Signal(
        dict, dict
    )  # image_map, payload with traces_path and seg_labeled
    status_message = Signal(str)  # Status messages
    error_message = Signal(str)  # Error messages
    loading_state_changed = Signal(bool)  # Loading state changes
    cell_selected = Signal(str)  # Cell selection events (left-click)
    trace_quality_toggled = Signal(str)  # Trace quality toggle events (right-click)
    frame_changed = Signal(int)  # Frame index changes
    loading_started = Signal()  # When image loading starts
    loading_finished = Signal(
        bool, str
    )  # When image loading finishes (success, message)

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
        self._canvas = MplCanvas(self)
        image_layout.addWidget(self._canvas)

        layout.addWidget(image_group)

    def _build_controls_section(self) -> QVBoxLayout:
        """Build the controls section of the UI."""
        controls_layout = QVBoxLayout()

        # Data type selection row
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Data Type:"))
        self._data_type_combo = QComboBox()
        first_row.addWidget(self._data_type_combo)
        first_row.addStretch()
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
        self._data_type_combo.currentTextChanged.connect(self._on_data_type_selected)

        # Frame navigation
        self.prev_frame_button.clicked.connect(self._on_prev_frame_clicked)
        self.next_frame_button.clicked.connect(self._on_next_frame_clicked)
        self.prev_frame_10_button.clicked.connect(self._on_prev_frame_10_clicked)
        self.next_frame_10_button.clicked.connect(self._on_next_frame_10_clicked)

        # Canvas interactions
        self._canvas.artist_picked.connect(self._on_artist_picked)
        self._canvas.artist_right_clicked.connect(self._on_artist_right_clicked)

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot()
    def _on_progress_updated(self, message: str) -> None:
        """Handle progress updates from worker."""
        self.status_message.emit(message)

    @Slot(str)
    def _on_artist_picked(self, artist_id: str):
        """Handle artist left-click events from the canvas."""
        logger.debug("UI Event: Artist left-clicked - %s", artist_id)
        if artist_id.startswith("cell_"):
            cell_id = artist_id.split("_")[1]
            logger.debug("UI Action: Cell selected - %s", cell_id)
            self.cell_selected.emit(cell_id)
        elif artist_id.startswith("trace_"):
            # Extract trace ID from overlay label (e.g., "trace_5" -> "5")
            trace_id = artist_id.split("_")[1]
            logger.debug("UI Action: Trace overlay left-clicked - %s", trace_id)
            self.cell_selected.emit(trace_id)

    @Slot(str)
    def _on_artist_right_clicked(self, artist_id: str):
        """Handle artist right-click events from the canvas."""
        logger.debug("UI Event: Artist right-clicked - %s", artist_id)
        if artist_id.startswith("trace_"):
            # Extract trace ID from overlay label (e.g., "trace_5" -> "5")
            trace_id = artist_id.split("_")[1]
            logger.debug("UI Action: Trace quality toggle - %s", trace_id)
            self.trace_quality_toggled.emit(trace_id)

    @Slot(str)
    def _on_data_type_selected(self, data_type: str):
        """Handle data type selection changes."""
        logger.debug("UI Event: Data type selected - %s", data_type)
        if data_type and data_type in self._image_cache:
            self._current_data_type = data_type
            self._render_current_frame()

    def _on_prev_frame_clicked(self):
        """Handle previous frame button click."""
        logger.debug("UI Click: Previous frame button")
        self.set_current_frame(self._current_frame_index - 1)

    def _on_next_frame_clicked(self):
        """Handle next frame button click."""
        logger.debug("UI Click: Next frame button")
        self.set_current_frame(self._current_frame_index + 1)

    def _on_prev_frame_10_clicked(self):
        """Handle previous 10 frames button click."""
        logger.debug("UI Click: Previous 10 frames button")
        self.set_current_frame(self._current_frame_index - 10)

    def _on_next_frame_10_clicked(self):
        """Handle next 10 frames button click."""
        logger.debug("UI Click: Next 10 frames button")
        self.set_current_frame(self._current_frame_index + 10)

    # ------------------------------------------------------------------------
    # VISUALIZATION REQUEST
    # ------------------------------------------------------------------------
    def on_visualization_requested(
        self, project_data: dict, fov_id: int, selected_channels: list[str]
    ):
        """Handle visualization requests from other components."""
        # Cancel any existing worker
        if self._worker:
            self._worker.stop()

        # Clear current state
        self.clear_all()

        # Start loading
        self.loading_state_changed.emit(True)
        self.loading_started.emit()
        self.status_message.emit(f"Loading FOV {fov_id:03d}…")

        # Create and start worker
        worker = VisualizationWorker(
            project_data=project_data,
            fov_id=fov_id,
            selected_channels=selected_channels,
        )
        worker.progress_updated.connect(self._on_progress_updated)
        worker.fov_data_loaded.connect(self._on_worker_fov_loaded)
        worker.error_occurred.connect(self._on_worker_error)
        worker.finished.connect(self._on_worker_finished)

        self._worker = start_worker(
            worker,
            start_method="process_fov_data",
            finished_callback=lambda: setattr(self, "_worker", None),
        )

    def _on_worker_fov_loaded(self, fov_id: int, image_map: dict, payload: dict):
        """Handle successful FOV data loading from worker."""
        logger.info("FOV %d data loaded with %d image types", fov_id, len(image_map))

        # Update image cache
        self._image_cache = image_map
        self._max_frame_index = max(
            (arr.shape[0] - 1 for arr in image_map.values() if arr.ndim == 3), default=0
        )

        # Update data type selector
        self._data_type_combo.blockSignals(True)
        self._data_type_combo.clear()
        self._data_type_combo.addItems(list(image_map.keys()))
        self._data_type_combo.blockSignals(False)

        # Select first data type
        if image_map:
            self._on_data_type_selected(next(iter(image_map.keys())))
        self.set_current_frame(0)

        # Emit signal for other components
        self.fov_data_loaded.emit(image_map, payload)

        # Update loading state
        self.loading_state_changed.emit(False)
        self.loading_finished.emit(True, "FOV loaded successfully")

    def _on_worker_error(self, message: str):
        """Handle worker errors."""
        logger.error("Visualization worker error: %s", message)
        self.error_message.emit(message)
        self.loading_state_changed.emit(False)

    def _on_worker_finished(self) -> None:
        """Handle worker completion."""
        logger.info("Visualization worker finished")
        self.loading_state_changed.emit(False)
        self.loading_finished.emit(True, "Visualization completed")

    # ------------------------------------------------------------------------
    # TRACE OVERLAY UPDATES
    # ------------------------------------------------------------------------
    def on_trace_positions_updated(self, overlays: dict):
        """Handle trace position overlay updates from trace panel.

        Args:
            overlays: Dict mapping overlay IDs to overlay properties
        """
        logger.debug(f"on_trace_positions_updated called with {len(overlays)} overlays")
        logger.debug(f"Overlay IDs: {list(overlays.keys())}")

        # Clear existing trace overlays
        existing_trace_overlays = [
            key
            for key in self._canvas._overlay_artists.keys()
            if key.startswith("trace_")
        ]
        logger.debug(f"Clearing {len(existing_trace_overlays)} existing trace overlays")
        for key in existing_trace_overlays:
            self._canvas.remove_overlay(key)

        # Add new overlays
        for overlay_id, properties in overlays.items():
            logger.debug(
                f"Adding overlay {overlay_id} at position {properties.get('xy')}"
            )
            self._canvas.plot_overlay(overlay_id, properties)

        logger.debug(
            f"Total overlays after update: {len(self._canvas._overlay_artists)}"
        )

    def on_active_trace_changed(self, trace_id: str | None):
        """Handle active trace changes from trace panel."""
        self._active_trace_id = trace_id
        self._render_current_frame()

    def clear_all(self):
        """Clear all cached data and reset UI state."""
        self._image_cache.clear()
        self._current_data_type = ""
        self.set_current_frame(0)
        self._max_frame_index = 0
        self._update_frame_label()
        self._data_type_combo.clear()
        self._canvas.clear()

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
        self.frame_changed.emit(self._current_frame_index)  # Notify trace panel

    def _render_current_frame(self):
        """Render the current frame with overlays."""
        image = self._image_cache.get(self._current_data_type)
        if image is None:
            self._canvas.clear()
            return

        # Get the current frame
        frame = image[self._current_frame_index] if image.ndim == 3 else image
        logger.debug(
            f"Rendering frame {self._current_frame_index}, shape: {frame.shape}"
        )
        cmap = "gray"
        self._canvas.plot_image(frame, cmap=cmap, vmin=frame.min(), vmax=frame.max())

        # Note: Overlays are managed by on_trace_positions_updated, not here
        # Don't clear overlays here as it would remove trace overlays

        # Update title
        self._canvas.axes.set_title(
            f"{self._current_data_type} - Frame {self._current_frame_index}"
        )

    def _update_frame_label(self):
        """Update the frame navigation label."""
        self.frame_label.setText(
            f"Frame {self._current_frame_index}/{self._max_frame_index}"
        )


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
        self, *, project_data: dict, fov_id: int, selected_channels: list[str]
    ):
        super().__init__()
        self._project_data = project_data
        self._fov_id = fov_id
        self._selected_channels = selected_channels

    # ------------------------------------------------------------------------
    # WORK EXECUTION
    # ------------------------------------------------------------------------
    def process_fov_data(self):
        """Process FOV data in background thread."""
        try:
            self.progress_updated.emit(f"Loading data for FOV {self._fov_id:03d}…")
            logger.debug(f"Processing FOV {self._fov_id}")

            # Get FOV data
            fov_data = self._project_data["fov_data"].get(self._fov_id)
            if not fov_data:
                logger.error(f"FOV {self._fov_id} not found in project data")
                self.error_occurred.emit(f"FOV {self._fov_id} not found.")
                return

            logger.debug(f"FOV {self._fov_id} data keys: {list(fov_data.keys())}")
            logger.debug(f"Selected channels: {self._selected_channels}")

            # Load selected channels
            image_map = {}
            for i, channel in enumerate(self._selected_channels, 1):
                self.progress_updated.emit(
                    f"Loading {channel} ({i}/{len(self._selected_channels)})…"
                )
                if channel not in fov_data:
                    logger.warning(f"Channel {channel} not found in FOV data")
                    continue

                path = Path(fov_data[channel])
                logger.debug(f"Loading channel {channel} from {path}")
                if path.exists():
                    image_data = np.load(path)
                    image_map[channel] = self._preprocess(image_data, channel)
                    logger.debug(f"Loaded {channel} with shape {image_data.shape}")
                else:
                    logger.warning(f"Channel file does not exist: {path}")

            if not image_map:
                logger.error("No image data found for selected channels")
                self.error_occurred.emit("No image data found for selected channels.")
                return

            logger.debug(f"Loaded {len(image_map)} channels successfully")

            # Load labeled segmentation if available
            seg_labeled_data = self._load_segmentation(fov_data)
            if seg_labeled_data is not None:
                logger.debug("Segmentation data loaded successfully")
            else:
                logger.debug("No segmentation data loaded")

            # Load trace paths for fluorescence channels
            traces_paths = self._get_trace_paths(fov_data)
            logger.debug(f"Found trace paths for channels: {list(traces_paths.keys())}")

            # Get time units from project data
            time_units = self._project_data.get("time_units", "min")

            # Create payload and emit signal
            payload = {
                "traces": traces_paths,
                "seg_labeled": seg_labeled_data,
                "time_units": time_units,
            }
            logger.debug(
                f"Emitting fov_data_loaded signal with payload keys: {list(payload.keys())}"
            )
            self.fov_data_loaded.emit(self._fov_id, image_map, payload)

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
        logger.debug(
            f"Looking for segmentation data. Available keys: {list(fov_data.keys())}"
        )

        # Try to find segmentation data with various key patterns
        seg_path = None
        seg_key = None

        # First try the legacy key
        if "segmentation_labeled" in fov_data:
            seg_key = "segmentation_labeled"
            seg_path = Path(fov_data[seg_key])
            logger.debug(f"Found legacy segmentation key: {seg_key}")
        else:
            # Try channel-specific keys (e.g., seg_labeled_ch_0)
            for key in fov_data.keys():
                if key.startswith("seg_labeled_ch_"):
                    seg_key = key
                    seg_path = Path(fov_data[key])
                    logger.debug(f"Found channel-specific segmentation key: {seg_key}")
                    break

        if seg_path is None:
            logger.debug("No segmentation data found in fov_data")
            return None

        logger.debug(f"Attempting to load segmentation from: {seg_path}")
        logger.debug(f"Segmentation file exists: {seg_path.exists()}")

        try:
            if seg_path.exists():
                # Load the first frame of the labeled segmentation
                seg_data = np.load(seg_path, mmap_mode="r")[0]
                logger.debug(
                    f"Successfully loaded segmentation data with shape: {seg_data.shape}"
                )
                return seg_data
            else:
                logger.warning(f"Segmentation file does not exist: {seg_path}")
        except Exception as e:
            logger.error(f"Failed to load segmentation from {seg_path}: {e}")
        return None

    def _get_trace_paths(self, fov_data: dict) -> dict[str, Path]:
        """Get trace file paths for all available fluorescence channels.

        Note: Trace CSVs are loaded independently of selected image channels.
        The channel selector only controls which images are loaded, but all
        available trace data should be accessible in the trace panel.
        """
        traces_paths = {}
        logger.debug("Looking for all available trace CSV files in fov_data")
        logger.debug(f"Available keys in fov_data: {list(fov_data.keys())}")

        # Search for all trace CSV files in the FOV data
        for key, value in fov_data.items():
            if key.startswith("traces_ch_"):
                # Extract channel index from key like "traces_ch_1"
                channel_id = key.split("_")[-1]
                trace_path = Path(value)
                if trace_path.exists():
                    traces_paths[channel_id] = trace_path
                    logger.debug(
                        f"Found trace file for channel {channel_id}: {trace_path}"
                    )
                else:
                    logger.warning(f"Trace file does not exist: {trace_path}")

        logger.debug(f"Final trace paths: {traces_paths}")
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
