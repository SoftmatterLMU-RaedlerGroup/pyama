"""Trace viewer panel for displaying and selecting time traces."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from dataclasses import fields as dataclass_fields
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor
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
from pyama_core.io.trace_paths import resolve_trace_path
from pyama_core.types.processing import Result
from pyama_pro.components.mpl_canvas import MplCanvas
from pyama_pro.types.visualization import FeatureData, PositionData

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN TRACE PANEL
# =============================================================================


class TracePanel(QWidget):
    """Panel to plot time traces and allow selection via a checkable table.

    This panel provides an interface for displaying and interacting with
    time trace data from microscopy processing results. It includes a
    plot area for visualizing trace features, a paginated list for
    selecting traces, and controls for managing trace quality and
    saving inspected data.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    active_trace_changed = Signal(str)  # Emitted when active trace ID changes
    error_message = Signal(str)  # Emitted when an error occurs
    positions_updated = Signal(dict)  # Emitted when cell position updates occur
    trace_positions_changed = Signal(dict)  # Emitted when trace positions change
    trace_data_loaded = Signal(
        bool, str
    )  # Emitted when trace data loading finishes (success, message)
    trace_data_saved = Signal(
        bool, str
    )  # Emitted when trace data saving finishes (success, message)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the trace panel.

        Args:
            *args: Positional arguments passed to parent QWidget
            **kwargs: Keyword arguments passed to parent QWidget
        """
        super().__init__(*args, **kwargs)
        self._build_ui()
        self._connect_signals()
        # State from Models
        self._trace_features: dict[str, FeatureData] = {}
        self._trace_positions: dict[str, PositionData] = {}  # Position data per trace
        self._good_status: dict[str, bool] = {}
        self._active_trace_id: str | None = None
        self._traces_csv_path: Path | None = None
        self._inspected_path: Path | None = None
        self._processing_df: pd.DataFrame | None = None
        self._time_units: str = "min"  # Default time units

        # UI State
        self._trace_ids: list[str] = []
        self._current_page = 0
        self._items_per_page = 10

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout.

        Creates a vertical layout with two main groups:
        1. Trace plot group with feature selection and matplotlib canvas
        2. Trace selection group with paginated list and controls
        """
        layout = QVBoxLayout(self)
        plot_group, list_group = self._build_groups()
        layout.addWidget(plot_group, 1)
        layout.addWidget(list_group, 1)

    def _build_groups(self) -> tuple[QGroupBox, QGroupBox]:
        """Build the plot and list groups.

        Returns:
            Tuple of (plot_group, list_group) QGroupBox widgets
        """
        # Build plot group
        plot_group = QGroupBox("Trace Plot")
        plot_layout = QVBoxLayout(plot_group)

        selection_row = QHBoxLayout()
        selection_row.addWidget(QLabel("Feature:"))
        self._feature_dropdown = QComboBox()
        selection_row.addWidget(self._feature_dropdown)
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
        self._trace_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )  # Enable right-click

        list_layout.addWidget(self._trace_list)

        # Pagination controls
        bottom_control = QVBoxLayout()
        pagination_row = QHBoxLayout()
        self._page_label = QLabel("Page 1 of 1:")
        self._prev_button = QPushButton("Previous")
        self._next_button = QPushButton("Next")
        pagination_row.addWidget(self._page_label)
        pagination_row.addWidget(self._prev_button)
        pagination_row.addWidget(self._next_button)
        bottom_control.addLayout(pagination_row)
        self._save_button = QPushButton("Save Inspected CSV")
        bottom_control.addWidget(self._save_button)
        list_layout.addLayout(bottom_control)

        return plot_group, list_group

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers.

        Sets up all the signal/slot connections for user interactions,
        including feature selection, trace selection, pagination, and saving.
        """
        self._feature_dropdown.currentTextChanged.connect(
            lambda: self._plot_current_page()
        )
        self._trace_list.itemClicked.connect(self._on_list_item_clicked)
        self._trace_list.customContextMenuRequested.connect(self._on_list_right_clicked)
        self._prev_button.clicked.connect(self._on_prev_page)
        self._next_button.clicked.connect(self._on_next_page)
        self._save_button.clicked.connect(self._on_save_clicked)

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot(QListWidgetItem)
    def _on_list_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle left-click on list item.

        Args:
            item: The clicked list item
        """
        trace_id = item.data(Qt.ItemDataRole.UserRole)
        if trace_id:
            logger.debug(
                "UI Event: Trace list left-click (trace_id=%s, page=%d, items_per_page=%d)",
                trace_id,
                self._current_page,
                self._items_per_page,
            )
            self._set_active_trace(trace_id)

    @Slot()
    @Slot(object)
    def _on_list_right_clicked(self, pos) -> None:
        """Handle right-click on list widget.

        Args:
            pos: Position of the right-click event
        """
        item = self._trace_list.itemAt(pos)
        if item:
            trace_id = item.data(Qt.ItemDataRole.UserRole)
            if trace_id:
                logger.debug(
                    "UI Event: Trace list right-click (trace_id=%s)", trace_id
                )
                self.on_trace_quality_toggled(trace_id)

    def on_cell_selected(self, cell_id: str) -> None:
        """Handle cell/trace selection from image panel (left-click).

        Args:
            cell_id: ID of the selected cell/trace
        """
        self._select_trace(cell_id)

    def on_trace_quality_toggled(self, trace_id: str) -> None:
        """Handle trace quality toggle from image panel (right-click).

        Args:
            trace_id: ID of the trace whose quality is being toggled
        """
        if trace_id not in self._good_status:
            logger.debug(
                "Trace %s not found in quality map (available=%d)",
                trace_id,
                len(self._good_status),
            )
            return

        # Toggle the quality status
        self._good_status[trace_id] = not self._good_status[trace_id]
        logger.debug(
            "Toggled trace %s quality to %s", trace_id, self._good_status[trace_id]
        )

        # If toggling to bad, deactivate it
        if not self._good_status[trace_id] and self._active_trace_id == trace_id:
            self._set_active_trace(None)

        # Update UI
        self._populate_table()
        self._plot_current_page()
        self._emit_position_overlays()

    def _on_artist_picked(self, artist_id: str) -> None:
        """Handle artist picked event from canvas.

        Args:
            artist_id: ID of the picked artist
        """
        if artist_id.startswith("cell_"):
            return  # Handled by ImagePanel
        self._select_trace(artist_id)

    def _select_trace(self, trace_id: str) -> None:
        """Select a trace by ID, switching pages if necessary.

        Args:
            trace_id: ID of the trace to select
        """
        if trace_id not in self._trace_ids:
            logger.debug(
                "Trace %s not found in trace list (available_ids=%d)",
                trace_id,
                len(self._trace_ids),
            )
            return

        logger.debug(
            "Selecting trace %s (current_page=%d, items_per_page=%d)",
            trace_id,
            self._current_page,
            self._items_per_page,
        )

        # Find the page for the trace
        try:
            index = self._trace_ids.index(trace_id)
            page = index // self._items_per_page
            if page != self._current_page:
                logger.debug(
                    "Switching page for trace selection (from=%d, to=%d)",
                    self._current_page,
                    page,
                )
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

    # =============================================================================
    # PUBLIC SLOTS
    # =============================================================================
    def on_fov_data_loaded(self, image_map: dict, payload: dict) -> None:
        """Handle FOV data loaded event from image panel.

        Args:
            image_map: Dictionary mapping data types to image arrays
            payload: Additional data including trace paths and segmentation
        """
        self.clear()
        traces_entry = payload.get("traces", {})

        # Extract time units from payload
        self._time_units = payload.get("time_units", "min")
        logger.debug("Time units set to: %s", self._time_units)

        candidate_paths: list[Path] = []
        if isinstance(traces_entry, dict):
            for value in traces_entry.values():
                path_obj = Path(value)
                if path_obj not in candidate_paths:
                    candidate_paths.append(path_obj)
        elif isinstance(traces_entry, (list, tuple)):
            for value in traces_entry:
                path_obj = Path(value)
                if path_obj not in candidate_paths:
                    candidate_paths.append(path_obj)
        elif traces_entry:
            candidate_paths.append(Path(traces_entry))

        if not candidate_paths:
            return

        if len(candidate_paths) > 1:
            logger.warning(
                "Multiple trace CSVs detected; defaulting to the first path: %s",
                candidate_paths[0],
            )

        self._load_data_from_csv(candidate_paths[0])

    # =============================================================================
    # INTERNAL LOGIC
    # =============================================================================
    def _load_data_from_csv(self, csv_path: Path) -> None:
        """Load trace data from CSV file.

        Args:
            csv_path: Path to the CSV file to load
        """
        path_to_load = resolve_trace_path(csv_path)
        if path_to_load is None:
            self.trace_data_loaded.emit(False, f"Invalid trace path: {csv_path}")
            return
        
        try:
            df = get_dataframe(path_to_load)
            base_fields = ["fov"] + [field.name for field in dataclass_fields(Result)]
            missing = [col for col in base_fields if col not in df.columns]
            if missing:
                raise ValueError(
                    f"Trace CSV is missing required columns: {', '.join(sorted(missing))}"
                )

            base_cols = [col for col in base_fields if col in df.columns]
            base_set = set(base_fields)
            feature_cols = [col for col in df.columns if col not in base_set]
            if not feature_cols:
                raise ValueError("Trace CSV contains no feature columns.")

            ordered_columns = list(dict.fromkeys(base_cols + feature_cols))
            self._processing_df = df[ordered_columns].copy()
            self._traces_csv_path = csv_path
            self._inspected_path = path_to_load  # Track which file was actually loaded
            self._extract_quality_and_features()
            self._update_ui_from_data()
            logger.info(
                "Trace CSV loaded: %s (rows=%d, features=%d)",
                path_to_load,
                len(self._processing_df),
                len(feature_cols),
            )
            self.trace_data_loaded.emit(
                True, f"{path_to_load.name} loaded from {path_to_load.parent}"
            )
        except Exception as e:
            logger.error("Failed to load trace data from %s: %s", path_to_load, e)
            self.trace_data_loaded.emit(False, f"Error loading traces: {e}")

    def _extract_quality_and_features(self) -> None:
        """Extract quality, features, and positions from the processing dataframe."""
        if self._processing_df is None:
            return

        # Use the core extraction function
        cells_data = extract_all_cells_data(self._processing_df)
        logger.debug("Extracted data for %d cells", len(cells_data))

        # Populate internal data structures
        for cell_id, data in cells_data.items():
            # Quality status
            self._good_status[cell_id] = data["quality"]

            # Features (frame series)
            frame = data["features"]["frame"]
            features = {k: v for k, v in data["features"].items() if k != "frame"}
            self._trace_features[cell_id] = FeatureData(
                frame_points=frame, features=features
            )

            # Positions (by frame)
            self._trace_positions[cell_id] = PositionData(
                frames=data["positions"]["frames"],
                position={
                    "x": data["positions"]["position_x"],
                    "y": data["positions"]["position_y"],
                },
            )
            logger.debug(
                "Extracted data for trace %s: %d frames (range=%s-%s)",
                cell_id,
                len(data["positions"]["frames"]),
                data["positions"]["frames"].min(),
                data["positions"]["frames"].max(),
            )

    def _update_ui_from_data(self) -> None:
        """Update UI elements with loaded trace data."""
        self._trace_ids = sorted(self._trace_features.keys(), key=int)
        self._current_page = 0
        self._update_pagination()
        self._update_feature_dropdown()
        self._populate_table()
        self._plot_current_page()
        self._emit_position_overlays()  # Show overlays for first page on initial load

    def _plot_current_page(self) -> None:
        """Plot traces for the current page."""
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
                lines.append((data.frame_points, data.features[feature]))
                styles.append(style)

        # Use frame as x-axis label
        x_label = "Frame"
        self._trace_canvas.plot_lines(
            lines,
            styles,
            title="",
            x_label=x_label,
            y_label=feature,
        )

    # ------------------------------------------------------------------------
    # UI UPDATES
    # ------------------------------------------------------------------------
    def _set_active_trace(self, trace_id: str | None) -> None:
        """Set the active trace and update UI accordingly.

        Args:
            trace_id: ID of the trace to set as active, or None to deactivate
        """
        if self._active_trace_id == trace_id:
            return
        self._active_trace_id = trace_id
        self._populate_table()  # Repopulate to update colors
        self._plot_current_page()
        self._emit_position_overlays()  # Update position overlays
        if trace_id:
            self.active_trace_changed.emit(trace_id)

    @Slot()
    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        if self._processing_df is None or self._traces_csv_path is None:
            self.trace_data_saved.emit(False, "No data to save.")
            return

        updated_quality = pd.DataFrame(
            self._good_status.items(), columns=["cell", "good"]
        )
        # Convert cell IDs to integers to match the processing DataFrame
        updated_quality["cell"] = updated_quality["cell"].astype(int)
        updated_df = update_cell_quality(self._processing_df, updated_quality)

        # If we loaded an inspected file, overwrite it; otherwise create new inspected file
        if self._inspected_path and self._inspected_path.name.endswith(
            "_inspected.csv"
        ):
            save_path = self._inspected_path
        else:
            save_path = self._traces_csv_path.with_name(
                f"{self._traces_csv_path.stem}_inspected.csv"
            )
        try:
            write_dataframe(updated_df, save_path)
            logger.info(
                "Saved inspected trace CSV to %s (rows=%d)",
                save_path,
                len(updated_df),
            )
            self.trace_data_saved.emit(
                True, f"{save_path.name} saved to {save_path.parent}"
            )
        except Exception as e:
            logger.error("Failed to save inspected data: %s", e)
            self.trace_data_saved.emit(False, f"Error saving data: {e}")

    def _set_all_good_status(self, is_good: bool) -> None:
        """Set all traces to the specified quality status.

        Args:
            is_good: Whether to mark all traces as good
        """
        for trace_id in self._trace_ids:
            self._good_status[trace_id] = is_good
        self._populate_table()
        self._plot_current_page()

    def _populate_table(self) -> None:
        """Populate the list widget with visible traces."""
        trace_ids = self._visible_trace_ids()
        self._trace_list.blockSignals(True)
        self._trace_list.clear()

        for tid in trace_ids:
            item = QListWidgetItem(f"Trace {tid}")
            item.setData(Qt.ItemDataRole.UserRole, tid)  # Store trace_id

            # Set text color based on quality and active state
            # Red: good + active, Blue: good + inactive, Green: bad
            is_good = self._good_status.get(tid, False)
            is_active = tid == self._active_trace_id

            if not is_good:
                color = QColor("green")
            elif is_active and is_good:
                color = QColor("red")
            else:
                color = QColor("blue")

            item.setForeground(color)
            self._trace_list.addItem(item)

        self._trace_list.blockSignals(False)

    def _update_pagination(self) -> None:
        """Update pagination controls."""
        total_pages = max(
            1, (len(self._trace_ids) + self._items_per_page - 1) // self._items_per_page
        )
        self._page_label.setText(f"Page {self._current_page + 1} of {total_pages}")
        self._prev_button.setEnabled(self._current_page > 0)
        self._next_button.setEnabled(self._current_page < total_pages - 1)

    @Slot()
    def _on_prev_page(self) -> None:
        """Handle previous page button click."""
        if self._current_page > 0:
            self._current_page -= 1
            self._set_active_trace(None)
            self._update_pagination()
            self._populate_table()
            self._plot_current_page()
            self._emit_position_overlays()  # Update overlays for new page

    @Slot()
    def _on_next_page(self) -> None:
        """Handle next page button click."""
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

    def _update_feature_dropdown(self) -> None:
        """Update the feature dropdown with available features."""
        self._feature_dropdown.blockSignals(True)
        self._feature_dropdown.clear()
        if self._trace_features:
            # Collect all unique features across all traces
            all_features = set()
            for trace_id, trace_data in self._trace_features.items():
                trace_features = list(trace_data.features.keys())
                logger.debug(
                    "Trace %s features detected: %s", trace_id, trace_features
                )
                all_features.update(trace_features)
            features = sorted(list(all_features))
            logger.debug("All unique features found (%d): %s", len(features), features)
            self._feature_dropdown.addItems(features)
        self._feature_dropdown.blockSignals(False)

    def _visible_trace_ids(self) -> list[str]:
        """Get the list of trace IDs visible on the current page.

        Returns:
            List of trace IDs visible on the current page
        """
        start = self._current_page * self._items_per_page
        return self._trace_ids[start : start + self._items_per_page]

    def _emit_position_overlays(self) -> None:
        """Emit position overlays for visible traces at the current frame."""
        if not hasattr(self, "_current_frame"):
            self._current_frame = 0

        logger.debug(
            "Emitting position overlays at frame %d (visible_traces=%d)",
            self._current_frame,
            len(self._visible_trace_ids()),
        )

        overlays = {}
        visible_ids = self._visible_trace_ids()
        logger.debug("Visible trace IDs: %s", visible_ids)
        logger.debug(
            "Available position data for traces: %s",
            list(self._trace_positions.keys()),
        )

        for trace_id in visible_ids:
            if trace_id not in self._trace_positions:
                logger.debug(
                    "Trace %s has no position data; skipping overlay", trace_id
                )
                continue

            pos_data = self._trace_positions[trace_id]
            logger.debug(
                "Trace %s frame availability: %s frames",
                trace_id,
                len(pos_data.frames),
            )

            # Find position at current frame
            frame_id = np.where(pos_data.frames == self._current_frame)[0]
            if len(frame_id) == 0:
                logger.debug(
                    "Trace %s has no position at frame %d",
                    trace_id,
                    self._current_frame,
                )
                continue

            id = frame_id[0]
            x = pos_data.position["x"][id]
            y = pos_data.position["y"][id]

            logger.debug(
                "Trace %s position at frame %d: (%.2f, %.2f)",
                trace_id,
                self._current_frame,
                x,
                y,
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

        logger.debug("Emitting %d overlays: %s", len(overlays), list(overlays.keys()))
        self.positions_updated.emit(overlays)

    def on_frame_changed(self, frame: int) -> None:
        """Handle frame changes from ImagePanel.

        Args:
            frame: New frame index
        """
        logger.debug("Frame changed to %d in trace panel", frame)
        self._current_frame = frame
        self._emit_position_overlays()

    def clear(self) -> None:
        """Clear all trace data and reset UI state."""
        self._trace_features.clear()
        self._trace_positions.clear()
        self._good_status.clear()
        self._trace_ids.clear()
        self._active_trace_id = None
        self._traces_csv_path = None
        self._inspected_path = None
        self._processing_df = None
        self._current_frame = 0
        self._trace_list.clear()
        self._trace_canvas.clear()
        self._feature_dropdown.clear()
        self._current_page = 0
        self._update_pagination()
        # Clear overlays
        self.positions_updated.emit({})
