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

from pyama_core.processing.workflow.services.types import Channels
from pyama_pro.utils import WorkerHandle, start_worker
from pyama_pro.types.visualization import PositionData
from pyama_pro.components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN IMAGE PANEL
# =============================================================================


class ImagePanel(QWidget):
    """Panel for viewing microscopy images and processing results.

    This panel provides an interface for displaying microscopy images
    and processing results, including frame navigation, data type
    selection, and interactive trace overlays. It handles loading
    of image data in background threads and provides signals for
    communication with other components.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    fov_data_loaded = Signal(
        dict, dict
    )  # Emitted when FOV data is loaded (image_map, payload with traces_path and seg_labeled)
    error_message = Signal(str)  # Emitted when an error occurs
    loading_state_changed = Signal(bool)  # Emitted when loading state changes
    cell_selected = Signal(str)  # Emitted when a cell is selected (left-click)
    trace_quality_toggled = Signal(
        str
    )  # Emitted when trace quality is toggled (right-click)
    frame_changed = Signal(int)  # Emitted when frame index changes

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the image panel.

        Args:
            *args: Positional arguments passed to parent QWidget
            **kwargs: Keyword arguments passed to parent QWidget
        """
        super().__init__(*args, **kwargs)
        self._initialize_state()
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # STATE INITIALIZATION
    # ------------------------------------------------------------------------
    def _initialize_state(self) -> None:
        """Initialize internal state variables.

        Sets up all the default values and state tracking variables
        used throughout the image panel, including image cache,
        frame navigation, and trace overlay state.
        """
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
        """Build the user interface layout.

        Creates a vertical layout with an image viewer group containing
        controls for data type selection and frame navigation, plus a
        matplotlib canvas for image display.
        """
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
        """Build the controls section of the UI.

        Returns:
            QVBoxLayout containing data type selection and frame navigation controls
        """
        controls_layout = QVBoxLayout()

        # Data type selection row
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Data Type:"))
        self._data_type_combo = QComboBox()
        first_row.addWidget(self._data_type_combo)
        controls_layout.addLayout(first_row)

        # Frame navigation row
        second_row = QHBoxLayout()
        self._prev_frame_10_button = QPushButton("<<")
        second_row.addWidget(self._prev_frame_10_button)
        self._prev_frame_button = QPushButton("<")
        second_row.addWidget(self._prev_frame_button)
        self._frame_label = QLabel("Frame 0/0")
        self._frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        second_row.addWidget(self._frame_label)
        self._next_frame_button = QPushButton(">")
        second_row.addWidget(self._next_frame_button)
        self._next_frame_10_button = QPushButton(">>")
        second_row.addWidget(self._next_frame_10_button)
        controls_layout.addLayout(second_row)

        return controls_layout

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers.

        Sets up all the signal/slot connections for user interactions,
        including data type selection, frame navigation, and canvas interactions.
        """
        # Data type selection
        self._data_type_combo.currentTextChanged.connect(self._on_data_type_selected)

        # Frame navigation
        self._prev_frame_button.clicked.connect(self._on_prev_frame_clicked)
        self._next_frame_button.clicked.connect(self._on_next_frame_clicked)
        self._prev_frame_10_button.clicked.connect(self._on_prev_frame_10_clicked)
        self._next_frame_10_button.clicked.connect(self._on_next_frame_10_clicked)

        # Canvas interactions
        self._canvas.artist_picked.connect(self._on_artist_picked)
        self._canvas.artist_right_clicked.connect(self._on_artist_right_clicked)

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot(str)
    def _on_artist_picked(self, artist_id: str) -> None:
        """Handle artist left-click events from the canvas.

        Args:
            artist_id: ID of the clicked artist element
        """
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
    def _on_artist_right_clicked(self, artist_id: str) -> None:
        """Handle artist right-click events from the canvas.

        Args:
            artist_id: ID of the right-clicked artist element
        """
        logger.debug("UI Event: Artist right-clicked - %s", artist_id)
        if artist_id.startswith("trace_"):
            # Extract trace ID from overlay label (e.g., "trace_5" -> "5")
            trace_id = artist_id.split("_")[1]
            logger.debug("UI Action: Trace quality toggle - %s", trace_id)
            self.trace_quality_toggled.emit(trace_id)

    @Slot(str)
    def _on_data_type_selected(self, data_type: str) -> None:
        """Handle data type selection changes.

        Args:
            data_type: Selected data type name
        """
        logger.debug("UI Event: Data type selected - %s", data_type)
        if data_type and data_type in self._image_cache:
            self._current_data_type = data_type
            self._render_current_frame()

    @Slot()
    def _on_prev_frame_clicked(self) -> None:
        """Handle previous frame button click."""
        logger.debug("UI Click: Previous frame button")
        self.set_current_frame(self._current_frame_index - 1)

    @Slot()
    def _on_next_frame_clicked(self) -> None:
        """Handle next frame button click."""
        logger.debug("UI Click: Next frame button")
        self.set_current_frame(self._current_frame_index + 1)

    @Slot()
    def _on_prev_frame_10_clicked(self) -> None:
        """Handle previous 10 frames button click."""
        logger.debug("UI Click: Previous 10 frames button")
        self.set_current_frame(self._current_frame_index - 10)

    @Slot()
    def _on_next_frame_10_clicked(self) -> None:
        """Handle next 10 frames button click."""
        logger.debug("UI Click: Next 10 frames button")
        self.set_current_frame(self._current_frame_index + 10)

    # ------------------------------------------------------------------------
    # VISUALIZATION REQUEST
    # ------------------------------------------------------------------------
    def on_visualization_requested(
        self, project_data: dict, fov_id: int, selected_channels: list[str]
    ) -> None:
        """Handle visualization requests from other components.

        Args:
            project_data: Dictionary containing project information
            fov_id: ID of the FOV to visualize
            selected_channels: List of channel names to load
        """
        # Cancel any existing worker
        if self._worker:
            self._worker.stop()

        # Clear current state
        self.clear_all()

        # Start loading
        self.loading_state_changed.emit(True)

        # Create and start worker
        worker = VisualizationWorker(
            project_data=project_data,
            fov_id=fov_id,
            selected_channels=selected_channels,
        )
        worker.finished.connect(self._on_worker_finished)

        self._worker = start_worker(
            worker,
            start_method="process_fov_data",
            finished_callback=lambda: setattr(self, "_worker", None),
        )

    def _on_worker_finished(self, success: bool, data: dict | None) -> None:
        """Handle worker completion.

        Args:
            success: Whether the operation succeeded
            data: Dictionary with fov_id, image_map, and payload if successful, None otherwise
        """
        self.loading_state_changed.emit(False)
        
        if success and data:
            fov_id = data["fov_id"]
            image_map = data["image_map"]
            payload = data["payload"]
            
            logger.info("FOV %d data loaded with %d image types", fov_id, len(image_map))

            # Update image cache
            self._image_cache = image_map
            self._max_frame_index = max(
                (arr.shape[0] - 1 for arr in image_map.values() if arr.ndim == 3), default=0
            )
            # Update frame label to reflect new max_frame_index
            self._update_frame_label()

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
        else:
            logger.error("Visualization worker failed: no data loaded")
            self.error_message.emit("Failed to load FOV data")

    # ------------------------------------------------------------------------
    # TRACE OVERLAY UPDATES
    # ------------------------------------------------------------------------
    def on_trace_positions_updated(self, overlays: dict) -> None:
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

    def on_active_trace_changed(self, trace_id: str | None) -> None:
        """Handle active trace changes from trace panel.

        Args:
            trace_id: ID of the newly active trace, or None if no trace is active
        """
        self._active_trace_id = trace_id
        self._render_current_frame()

    def clear_all(self) -> None:
        """Clear all cached data and reset UI state."""
        self._image_cache.clear()
        self._current_data_type = ""
        self.set_current_frame(0)
        self._max_frame_index = 0
        self._update_frame_label()
        self._data_type_combo.clear()
        self._canvas.clear()
        self._canvas.clear_overlays()

    # ------------------------------------------------------------------------
    # FRAME MANAGEMENT
    # ------------------------------------------------------------------------
    def set_current_frame(self, index: int) -> None:
        """Set the current frame index with bounds checking.

        Args:
            index: Frame index to set
        """
        if index < 0:
            index = 0
        elif index > self._max_frame_index:
            index = self._max_frame_index

        # Only update if the frame actually changed
        if index != self._current_frame_index:
            self._current_frame_index = index
            self._update_frame_label()
            self._render_current_frame()
            self.frame_changed.emit(self._current_frame_index)  # Notify trace panel

    def _render_current_frame(self) -> None:
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

        # No title

    def _update_frame_label(self) -> None:
        """Update the frame navigation label."""
        self._frame_label.setText(
            f"Frame {self._current_frame_index}/{self._max_frame_index}"
        )


# =============================================================================
# BACKGROUND VISUALIZATION WORKER
# =============================================================================


class VisualizationWorker(QObject):
    """Worker for loading and preprocessing FOV data in background.

    This class handles loading of image data, segmentation data, and trace
    paths in a separate thread to prevent blocking the UI during long
    loading operations. Progress updates are logged directly using logger.info().
    Completion signals are emitted for UI coordination.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    finished = Signal(bool, object)  # Emitted when worker completes (success, data_dict or None)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(
        self, *, project_data: dict, fov_id: int, selected_channels: list[str]
    ) -> None:
        """Initialize the visualization worker.

        Args:
            project_data: Dictionary containing project information
            fov_id: ID of the FOV to process
            selected_channels: List of channel names to load
        """
        super().__init__()
        self._project_data = project_data
        self._fov_id = fov_id
        self._selected_channels = selected_channels

    # ------------------------------------------------------------------------
    # WORK EXECUTION
    # ------------------------------------------------------------------------
    def process_fov_data(self) -> None:
        """Process FOV data in background thread.

        Loads image data, segmentation data, and trace paths for the specified
        FOV and channels. Progress updates are logged using logger.info().
        Completion signals are emitted when finished or if an error occurs.
        """
        try:
            logger.info("Loading data for FOV %03d", self._fov_id)
            logger.debug(f"Processing FOV {self._fov_id}")

            # Get FOV data
            fov_data = self._project_data["fov_data"].get(self._fov_id)
            if not fov_data:
                logger.error(f"FOV {self._fov_id} not found in project data")
                self.finished.emit(False, None)
                return

            logger.debug(f"FOV {self._fov_id} data keys: {list(fov_data.keys())}")
            logger.debug(f"Selected channels: {self._selected_channels}")

            # Load selected channels
            image_map = {}
            for i, channel in enumerate(self._selected_channels, 1):
                logger.info("Loading %s (%d/%d)", channel, i, len(self._selected_channels))
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
                self.finished.emit(False, None)
                return

            logger.debug(f"Loaded {len(image_map)} channels successfully")

            # Extract segmentation data from loaded channels if available
            seg_labeled_data = None
            for channel_name, image_data in image_map.items():
                if channel_name.startswith("seg_labeled_ch_"):
                    # Use first frame of segmentation data
                    seg_labeled_data = (
                        image_data[0] if image_data.ndim == 3 else image_data
                    )
                    logger.debug(f"Found segmentation data in channel: {channel_name}")
                    break

            if seg_labeled_data is not None:
                logger.debug("Segmentation data extracted from loaded channels")
            else:
                logger.debug("No segmentation data found in selected channels")

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
            # Emit finished signal with loaded data
            data_dict = {
                "fov_id": self._fov_id,
                "image_map": image_map,
                "payload": payload,
            }
            self.finished.emit(True, data_dict)

        except Exception:
            logger.exception("Error processing FOV data")
            self.finished.emit(False, None)

    # ------------------------------------------------------------------------
    # DATA LOADING HELPERS
    # ------------------------------------------------------------------------

    def _get_trace_paths(self, fov_data: dict) -> dict[str, Path]:
        """Get trace file paths for all available fluorescence channels.

        Note: Trace CSVs are loaded independently of selected image channels.
        The channel selector only controls which images are loaded, but all
        available trace data should be accessible in the trace panel.

        Args:
            fov_data: Dictionary containing FOV data paths

        Returns:
            Dictionary mapping channel IDs to trace file paths
        """
        traces_paths = {}
        logger.debug("Looking for all available trace CSV files in fov_data")
        logger.debug(f"Available keys in fov_data: {list(fov_data.keys())}")

        # Preferred combined traces file
        combined_path = fov_data.get("traces")
        if combined_path:
            trace_path = Path(combined_path)
            if trace_path.exists():
                channels_info = self._project_data.get("channels")
                if not isinstance(channels_info, dict):
                    channels_info = {}
                from pyama_core.processing.workflow.services.types import (
                    get_pc_channel,
                    normalize_channels,
                )
                if not isinstance(channels_info, dict):
                    channels_info = {}
                try:
                    channels_model: Channels = channels_info
                    normalize_channels(channels_model)
                except ValueError as exc:  # pragma: no cover - defensive path
                    logger.warning("Invalid channels metadata: %s", exc)
                    channels_model = {"fl": []}
                channel_ids: set[str] = set()
                pc_channel = get_pc_channel(channels_model)
                if pc_channel is not None:
                    channel_ids.add(str(pc_channel))
                for selection in channels_model.get("fl", []):
                    channel_ids.add(str(selection.get("channel", 0)))

                if not channel_ids:
                    logger.debug(
                        "No channel metadata available; defaulting to single combined trace path"
                    )
                    channel_ids.add("0")

                for channel_id in sorted(channel_ids, key=lambda x: int(x)):
                    traces_paths[channel_id] = trace_path
            else:
                logger.warning(f"Combined trace file does not exist: {trace_path}")
        else:
            # Legacy per-channel trace files
            for key, value in fov_data.items():
                if key.startswith("traces_ch_"):
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
        """Preprocess image data based on data type.

        Args:
            data: Raw image data array
            dtype: Data type identifier

        Returns:
            Preprocessed image data array
        """
        if dtype.startswith("seg"):
            return data.astype(np.uint8)
        if data.ndim == 3:
            return np.stack([self._normalize(f) for f in data])
        return self._normalize(data)

    def _normalize(self, frame: np.ndarray) -> np.ndarray:
        """Normalize frame to uint8 range using percentile stretching.

        Args:
            frame: Image frame to normalize

        Returns:
            Normalized frame with uint8 data type
        """
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
