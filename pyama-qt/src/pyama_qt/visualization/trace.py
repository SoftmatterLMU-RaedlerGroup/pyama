"""Trace viewer panel for displaying and selecting time traces."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from pathlib import Path
from dataclasses import dataclass

import pandas as pd
import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_core.io.processing_csv import (
    get_dataframe,
    extract_all_cells_data,
    update_cell_quality,
    write_dataframe,
)

from ..components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class FeatureData:
    """Data structure for cell feature time series."""

    time_points: np.ndarray
    features: dict[
        str, np.ndarray
    ]  # {"feature_name1": array, "feature_name2": array, ...}


@dataclass
class PositionData:
    """Data structure for cell position over frames."""

    frames: np.ndarray  # Frame numbers
    position_x: np.ndarray  # X positions per frame
    position_y: np.ndarray  # Y positions per frame


# =============================================================================
# MAIN TRACE PANEL
# =============================================================================


class TracePanel(QWidget):
    """Panel to plot time traces and allow selection via a checkable table."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    active_trace_changed = Signal(str)  # Active trace ID changes
    status_message = Signal(str)  # Status messages
    error_message = Signal(str)  # Error messages
    positions_updated = Signal(dict)  # Cell position updates

    trace_positions_changed = Signal(dict)
    status_message = Signal(str)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._build_ui()
        self._connect_signals()
        # --- State from Models ---
        self._trace_features: dict[str, FeatureData] = {}
        self._trace_positions: dict[str, PositionData] = {}  # Position data per trace
        self._good_status: dict[str, bool] = {}
        self._active_trace_id: str | None = None
        self._traces_csv_path: Path | None = None
        self._processing_df: pd.DataFrame | None = None
        self._trace_paths: dict[str, Path] = {}
        self._time_units: str = "min"  # Default time units

        # --- UI State ---
        self._trace_ids: list[str] = []
        self._current_page = 0
        self._items_per_page = 10

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout."""
        layout = QVBoxLayout(self)
        plot_group, list_group = self._build_groups()
        layout.addWidget(plot_group, 1)
        layout.addWidget(list_group, 1)

    def _build_groups(self) -> tuple[QGroupBox, QGroupBox]:
        """Build the plot and list groups."""
        # Build plot group
        plot_group = QGroupBox("Trace Plot")
        plot_layout = QVBoxLayout(plot_group)

        # Channel selection (at top of plot)
        selection_row = QHBoxLayout()
        selection_row.addWidget(QLabel("Channel:"))
        self._channel_dropdown = QComboBox()
        selection_row.addWidget(self._channel_dropdown)

        # Feature selection (at top of plot)
        selection_row.addWidget(QLabel("Feature:"))
        self._feature_dropdown = QComboBox()
        selection_row.addWidget(self._feature_dropdown)

        selection_row.addStretch()

        plot_layout.addLayout(selection_row)

        # Canvas
        self._trace_canvas = MplCanvas(self)
        plot_layout.addWidget(self._trace_canvas)

        # Build list group
        list_group = QGroupBox("Trace Selection")
        list_layout = QVBoxLayout(list_group)

        # List widget for traces
        self._trace_list = QListWidget()
        self._trace_list.setSelectionMode(
            QListWidget.SelectionMode.NoSelection
        )  # No selection highlighting
        self._trace_list.setContextMenuPolicy(Qt.CustomContextMenu)  # Enable right-click

        list_layout.addWidget(self._trace_list)

        # Pagination controls
        pagination_row = QHBoxLayout()
        self._page_label = QLabel("Page 1 of 1:")
        self._prev_button = QPushButton("Previous")
        self._next_button = QPushButton("Next")
        self.save_button = QPushButton("Save Inspected CSV")
        pagination_row.addWidget(self._page_label)
        pagination_row.addWidget(self._prev_button)
        pagination_row.addWidget(self._next_button)
        pagination_row.addWidget(self.save_button)
        pagination_row.addStretch()
        list_layout.addLayout(pagination_row)

        return plot_group, list_group

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers."""
        self._channel_dropdown.currentIndexChanged.connect(self._on_channel_selected)
        self._feature_dropdown.currentTextChanged.connect(
            lambda: self._plot_current_page()
        )
        self._trace_list.itemClicked.connect(self._on_list_item_clicked)
        self._trace_list.customContextMenuRequested.connect(self._on_list_right_clicked)
        self._prev_button.clicked.connect(self._on_prev_page)
        self._next_button.clicked.connect(self._on_next_page)
        self.save_button.clicked.connect(self._on_save_clicked)

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    def _on_list_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle left-click on list item."""
        trace_id = item.data(Qt.UserRole)
        if trace_id:
            logger.debug(f"List item left-clicked: {trace_id}")
            self._set_active_trace(trace_id)

    def _on_list_right_clicked(self, pos) -> None:
        """Handle right-click on list widget."""
        item = self._trace_list.itemAt(pos)
        if item:
            trace_id = item.data(Qt.UserRole)
            if trace_id:
                logger.debug(f"List item right-clicked: {trace_id}")
                self.on_trace_quality_toggled(trace_id)

    def _plot_current_page(self) -> None:
        """Plot the current page of traces."""
        # Implementation would plot traces for current page
        pass

    def _on_channel_selected(self, index: int):
        if index < 0:
            return
        channel = self._channel_dropdown.itemData(index)
        if channel and channel in self._trace_paths:
            self._load_data_from_csv(self._trace_paths[channel])

    def on_cell_selected(self, cell_id: str):
        """Handle cell/trace selection from image panel (left-click)."""
        self._select_trace(cell_id)

    def on_trace_quality_toggled(self, trace_id: str):
        """Handle trace quality toggle from image panel (right-click)."""
        if trace_id not in self._good_status:
            logger.debug(f"Trace {trace_id} not found in good_status")
            return

        # Toggle the quality status
        self._good_status[trace_id] = not self._good_status[trace_id]
        logger.debug(
            f"Toggled trace {trace_id} quality to {self._good_status[trace_id]}"
        )

        # If toggling to bad, deactivate it
        if not self._good_status[trace_id] and self._active_trace_id == trace_id:
            self._set_active_trace(None)

        # Update UI
        self._populate_table()
        self._plot_current_page()
        self._emit_position_overlays()

    def _on_artist_picked(self, artist_id: str):
        if artist_id.startswith("cell_"):
            return  # Handled by ImagePanel
        self._select_trace(artist_id)

    def _select_trace(self, trace_id: str):
        """Select a trace by ID, switching pages if necessary."""
        if trace_id not in self._trace_ids:
            logger.debug(f"Trace {trace_id} not found in trace list")
            return

        logger.debug(f"Selecting trace {trace_id}")

        # Find the page for the trace
        try:
            index = self._trace_ids.index(trace_id)
            page = index // self._items_per_page
            if page != self._current_page:
                logger.debug(f"Switching from page {self._current_page} to page {page}")
                self._current_page = page
                self._update_pagination()
                self._populate_table()

            # Find the item in the current (now correct) page
            item_index = index % self._items_per_page
            self._trace_list.setCurrentRow(item_index)
            self._set_active_trace(trace_id)

        except ValueError:
            # Should not happen if trace_id is in self._trace_ids
            logger.error(f"ValueError when selecting trace {trace_id}")

    # --- Public Slots ---
    def on_fov_data_loaded(self, image_map: dict, payload: dict):
        self.clear()
        self._trace_paths = payload.get("traces", {})
        if not self._trace_paths:
            self.status_message.emit("No trace data found for this FOV.")
            return

        # Extract time units from payload
        self._time_units = payload.get("time_units", "min")
        logger.debug(f"Time units set to: {self._time_units}")

        self._channel_dropdown.blockSignals(True)
        self._channel_dropdown.clear()
        for ch in sorted(self._trace_paths.keys()):
            self._channel_dropdown.addItem(f"{ch}", ch)
        self._channel_dropdown.blockSignals(False)

        # Load data for the first channel
        first_channel = sorted(self._trace_paths.keys())[0]
        self._load_data_from_csv(self._trace_paths[first_channel])

    # --- Internal Logic ---
    def _load_data_from_csv(self, csv_path: Path):
        inspected_path = csv_path.with_name(
            f"{csv_path.stem}_inspected{csv_path.suffix}"
        )
        path_to_load = inspected_path if inspected_path.exists() else csv_path
        try:
            self._processing_df = get_dataframe(path_to_load)
            # Store the original CSV path for saving
            self._traces_csv_path = csv_path
            self._extract_quality_and_features()
            self._update_ui_from_data()
            self.status_message.emit(f"Loaded {len(self._trace_ids)} traces.")
        except Exception as e:
            logger.error("Failed to load trace data from %s: %s", path_to_load, e)
            self.status_message.emit(f"Error loading traces: {e}")

    def _extract_quality_and_features(self):
        """Extract quality, features, and positions from the processing dataframe."""
        if self._processing_df is None:
            return

        # Use the core extraction function
        cells_data = extract_all_cells_data(self._processing_df)
        logger.debug(f"Extracted data for {len(cells_data)} cells")

        # Populate internal data structures
        for cell_id, data in cells_data.items():
            # Quality status
            self._good_status[cell_id] = data["quality"]

            # Features (time series)
            time = data["features"]["time"]
            features = {k: v for k, v in data["features"].items() if k != "time"}
            self._trace_features[cell_id] = FeatureData(
                time_points=time, features=features
            )

            # Positions (by frame)
            self._trace_positions[cell_id] = PositionData(
                frames=data["positions"]["frames"],
                position_x=data["positions"]["position_x"],
                position_y=data["positions"]["position_y"],
            )
            logger.debug(
                f"Extracted data for trace {cell_id}: "
                f"{len(data['positions']['frames'])} frames, "
                f"frame range [{data['positions']['frames'].min()}, {data['positions']['frames'].max()}]"
            )

    def _update_ui_from_data(self):
        self._trace_ids = sorted(self._trace_features.keys(), key=int)
        self._current_page = 0
        self._update_pagination()
        self._update_feature_dropdown()
        self._populate_table()
        self._plot_current_page()
        self._emit_position_overlays()  # Show overlays for first page on initial load

    def _plot_current_page(self):
        feature = self._feature_dropdown.currentText()
        if not feature or not self._trace_ids:
            self._trace_canvas.clear()
            return

        lines, styles = [], []
        for trace_id in self._visible_trace_ids():
            data = self._trace_features.get(trace_id)
            if data and feature in data.features:
                # Determine color based on quality and active state
                # Red: good + active, Blue: good + inactive, Green: bad
                is_good = self._good_status.get(trace_id, False)
                is_active = trace_id == self._active_trace_id

                if not is_good:
                    color = "green"
                    alpha = 0.5
                    linewidth = 1
                elif is_active and is_good:
                    color = "red"
                    alpha = 1.0
                    linewidth = 2
                else:
                    color = "blue"
                    alpha = 0.5
                    linewidth = 1

                style = {"color": color, "alpha": alpha, "linewidth": linewidth}
                lines.append((data.time_points, data.features[feature]))
                styles.append(style)

        # Use time units in x-axis label
        x_label = f"Time ({self._time_units})"
        self._trace_canvas.plot_lines(
            lines,
            styles,
            title=f"{feature} over time",
            x_label=x_label,
            y_label=feature,
        )

    # --- Event Handlers & UI Updates ---
    def _set_active_trace(self, trace_id: str | None):
        if self._active_trace_id == trace_id:
            return
        self._active_trace_id = trace_id
        self._populate_table()  # Repopulate to update colors
        self._plot_current_page()
        self._emit_position_overlays()  # Update position overlays
        if trace_id:
            self.active_trace_changed.emit(trace_id)

    def _on_save_clicked(self):
        if self._processing_df is None or self._traces_csv_path is None:
            self.status_message.emit("No data to save.")
            return

        updated_quality = pd.DataFrame(
            self._good_status.items(), columns=["cell", "good"]
        )
        updated_df = update_cell_quality(self._processing_df, updated_quality)
        save_path = self._traces_csv_path.with_name(
            f"{self._traces_csv_path.stem}_inspected.csv"
        )
        try:
            write_dataframe(updated_df, save_path)
            self.status_message.emit(f"Saved inspected data to {save_path.name}")
        except Exception as e:
            logger.error("Failed to save inspected data: %s", e)
            self.status_message.emit(f"Error saving data: {e}")

    def _set_all_good_status(self, is_good: bool):
        for trace_id in self._trace_ids:
            self._good_status[trace_id] = is_good
        self._populate_table()
        self._plot_current_page()

    def _populate_table(self):
        """Populate the list widget with visible traces."""
        trace_ids = self._visible_trace_ids()
        self._trace_list.blockSignals(True)
        self._trace_list.clear()

        for tid in trace_ids:
            item = QListWidgetItem(f"Trace {tid}")
            item.setData(Qt.UserRole, tid)  # Store trace_id

            # Set text color based on quality and active state
            # Red: good + active, Blue: good + inactive, Green: bad
            is_good = self._good_status.get(tid, False)
            is_active = tid == self._active_trace_id

            if not is_good:
                color = Qt.green
            elif is_active and is_good:
                color = Qt.red
            else:
                color = Qt.blue

            item.setForeground(color)
            self._trace_list.addItem(item)

        self._trace_list.blockSignals(False)

    def _update_pagination(self):
        total_pages = max(
            1, (len(self._trace_ids) + self._items_per_page - 1) // self._items_per_page
        )
        self._page_label.setText(f"Page {self._current_page + 1} of {total_pages}")
        self._prev_button.setEnabled(self._current_page > 0)
        self._next_button.setEnabled(self._current_page < total_pages - 1)

    def _on_prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._set_active_trace(None)
            self._update_pagination()
            self._populate_table()
            self._plot_current_page()
            self._emit_position_overlays()  # Update overlays for new page

    def _on_next_page(self):
        total_pages = (
            len(self._trace_ids) + self._items_per_page - 1
        ) // self._items_per_page
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._set_active_trace(None)
            self._update_pagination()
            self._populate_table()
            self._plot_current_page()
            self._emit_position_overlays()  # Update overlays for new page

    def _update_feature_dropdown(self):
        self._feature_dropdown.blockSignals(True)
        self._feature_dropdown.clear()
        if self._trace_features:
            features = list(next(iter(self._trace_features.values())).features.keys())
            self._feature_dropdown.addItems(features)
        self._feature_dropdown.blockSignals(False)

    def _visible_trace_ids(self) -> list[str]:
        start = self._current_page * self._items_per_page
        return self._trace_ids[start : start + self._items_per_page]

    def _emit_position_overlays(self):
        """Emit position overlays for visible traces at the current frame."""
        if not hasattr(self, "_current_frame"):
            self._current_frame = 0

        logger.debug(
            f"_emit_position_overlays called. Current frame: {self._current_frame}"
        )

        overlays = {}
        visible_ids = self._visible_trace_ids()
        logger.debug(f"Visible trace IDs: {visible_ids}")
        logger.debug(
            f"Available position data for traces: {list(self._trace_positions.keys())}"
        )

        for trace_id in visible_ids:
            if trace_id not in self._trace_positions:
                logger.debug(f"Trace {trace_id} has no position data")
                continue

            pos_data = self._trace_positions[trace_id]
            logger.debug(f"Trace {trace_id} - frames available: {pos_data.frames}")

            # Find position at current frame
            frame_idx = np.where(pos_data.frames == self._current_frame)[0]
            if len(frame_idx) == 0:
                logger.debug(
                    f"Trace {trace_id} - no position at frame {self._current_frame}"
                )
                continue

            idx = frame_idx[0]
            x = pos_data.position_x[idx]
            y = pos_data.position_y[idx]

            logger.debug(
                f"Trace {trace_id} - position at frame {self._current_frame}: ({x}, {y})"
            )

            # Determine color based on quality and active state:
            # - Red: good and active
            # - Blue: good and inactive
            # - Green: bad (can't be active)
            is_good = self._good_status.get(trace_id, False)
            is_active = trace_id == self._active_trace_id and is_good

            if not is_good:
                color = "green"
            elif is_active:
                color = "red"
            else:
                color = "blue"

            overlays[f"trace_{trace_id}"] = {
                "type": "circle",
                "xy": (x, y),
                "radius": 40,
                "edgecolor": color,
                "facecolor": "none",
                "linewidth": 2.0,
                "alpha": 1.0,
                "zorder": 10,  # High z-order to ensure overlays are visible above image
            }

        logger.debug(f"Emitting {len(overlays)} overlays: {list(overlays.keys())}")
        self.positions_updated.emit(overlays)

    def on_frame_changed(self, frame: int):
        """Handle frame changes from ImagePanel."""
        logger.debug(f"on_frame_changed called with frame: {frame}")
        self._current_frame = frame
        self._emit_position_overlays()

    def clear(self):
        self._trace_features.clear()
        self._trace_positions.clear()
        self._good_status.clear()
        self._trace_ids.clear()
        self._trace_paths.clear()
        self._active_trace_id = None
        self._traces_csv_path = None
        self._processing_df = None
        self._current_frame = 0
        self._trace_list.clear()
        self._trace_canvas.clear()
        self._feature_dropdown.clear()
        self._channel_dropdown.clear()
        self._current_page = 0
        self._update_pagination()
        # Clear overlays
        self.positions_updated.emit({})
