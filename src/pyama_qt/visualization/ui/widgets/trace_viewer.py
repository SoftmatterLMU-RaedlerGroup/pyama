"""
Trace viewer widget for displaying and selecting time traces.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QMessageBox,
    QComboBox,
    QLabel,
)
from PySide6.QtCore import Qt, Signal, QEvent

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from pathlib import Path
from pyama_qt.core.cell_feature import FEATURE_EXTRACTORS


class TraceViewer(QWidget):
    """Widget to plot time traces and allow selection via a checkable table.

    Layout:
      - Fixed vertical layout (no splitter)
        - Top: Matplotlib plot area for traces
        - Bottom: Checkable list of available traces
    """

    # Emitted when the user changes which traces are checked
    selection_changed = Signal(list)  # list of identifiers for selected traces
    # Emitted when a checked trace ID cell is clicked to set it active/highlighted
    active_trace_changed = Signal(str)

    def __init__(self):
        super().__init__()

        self._trace_ids: list[str] = []
        self._feature_series: dict[str, dict[str, np.ndarray]] = {}  # {feature_name: {cell_id: series}}
        self._available_features: list[str] = []
        self._active_trace_id: str | None = None
        self._frames: np.ndarray = np.array([], dtype=float)
        self._traces_csv_path: Path | None = None
        self._current_trace_type: str | None = None
        self._good_status: dict[str, bool] = {}  # Track good/bad status

        # Single plot widget
        self._figure: Figure | None = None
        self._canvas: FigureCanvas | None = None
        self._axes: any | None = None
        self._feature_dropdown: QComboBox | None = None

        self._setup_ui()
        # Initially disabled until traces are available
        self.setEnabled(False)
        # Real data will be provided by the main window once a FOV is ready

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Top: Plot area with dropdown selector
        plot_group = QGroupBox("Traces")
        plot_vbox = QVBoxLayout(plot_group)

        # Feature selector dropdown
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Feature:"))
        self._feature_dropdown = QComboBox()
        self._feature_dropdown.currentTextChanged.connect(self._on_feature_changed)
        selector_layout.addWidget(self._feature_dropdown, 1)
        selector_layout.addStretch()
        plot_vbox.addLayout(selector_layout)

        # Create matplotlib figure and canvas
        self._figure = Figure(figsize=(8, 6), constrained_layout=True)
        self._canvas = FigureCanvas(self._figure)
        self._axes = self._figure.add_subplot(111)

        # Setup default blank plot
        self._axes.set_xticks([])
        self._axes.set_yticks([])
        self._canvas.draw_idle()

        plot_vbox.addWidget(self._canvas)
        layout.addWidget(plot_group, 1)

        # Bottom: Selection table
        list_group = QGroupBox("Trace Selection")
        list_vbox = QVBoxLayout(list_group)
        self._table_widget = QTableWidget()
        self._table_widget.setColumnCount(2)
        self._table_widget.setHorizontalHeaderLabels(["", "Trace ID"])
        self._table_widget.verticalHeader().setVisible(False)
        header = self._table_widget.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_header_section_clicked)
        self._table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table_widget.itemChanged.connect(self._on_item_changed)
        self._table_widget.cellClicked.connect(self._on_cell_clicked)
        # Column widths
        self._table_widget.setColumnWidth(0, 36)  # Checkbox
        # Add a visual hint in the header for toggling all/none
        header_hint_item = QTableWidgetItem("☐")
        header_hint_item.setToolTip("Click to toggle check all/none")
        header_hint_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table_widget.setHorizontalHeaderItem(0, header_hint_item)
        list_vbox.addWidget(self._table_widget)

        # Save button under the table
        self._save_button = QPushButton("Save 'good' traces")
        self._save_button.setToolTip("Write a new CSV with a 'good' column based on checked rows")
        self._save_button.clicked.connect(self._on_save_clicked)
        self._save_button.setEnabled(False)
        list_vbox.addWidget(self._save_button)
        layout.addWidget(list_group, 1)

    def _update_feature_dropdown(self) -> None:
        """Update dropdown menu with available features."""
        self._feature_dropdown.blockSignals(True)
        self._feature_dropdown.clear()

        for feature_name in self._available_features:
            display_name = feature_name.replace('_', ' ').title()
            self._feature_dropdown.addItem(display_name, feature_name)

        # Select first feature if available
        if self._available_features:
            self._feature_dropdown.setCurrentIndex(0)
            self._current_trace_type = self._available_features[0]

        self._feature_dropdown.blockSignals(False)

    # ---- Public API (to be wired in later steps) ----
    def clear(self) -> None:
        """Clear plot and list."""
        self._trace_ids.clear()
        self._active_trace_id = None
        self._feature_series.clear()
        self._available_features.clear()
        self._good_status.clear()

        if hasattr(self, "_table_widget"):
            self._table_widget.blockSignals(True)
            self._table_widget.setRowCount(0)
            self._table_widget.blockSignals(False)

        # Clear the plot
        if self._axes:
            self._axes.cla()
            self._axes.set_xlabel("Frame")
            self._axes.set_ylabel("Intensity")
            self._axes.grid(True, linestyle=":", linewidth=0.5)
            self._canvas.draw_idle()

        # Clear dropdown
        if self._feature_dropdown:
            self._feature_dropdown.clear()

        self.setEnabled(False)

    def set_traces(self, trace_ids: list[str], good_status: dict[str, bool] | None = None) -> None:
        """Populate the selection list with provided trace identifiers.

        Args:
            trace_ids: List of trace identifiers to display
            good_status: Optional dict mapping trace_id to good/bad status
        """
        # Only clear the table and trace list, not the feature data
        self._trace_ids = list(trace_ids)
        self._active_trace_id = None

        # Store good status if provided
        if good_status:
            self._good_status = good_status.copy()
        else:
            # Default all to True if not provided
            self._good_status = {tid: True for tid in self._trace_ids}

        self._table_widget.blockSignals(True)
        self._table_widget.setRowCount(len(self._trace_ids))
        for row, trace_id in enumerate(self._trace_ids):
            # Checkbox item (column 0) - initialize based on good status
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            is_good = self._good_status.get(trace_id, True)
            check_item.setCheckState(Qt.CheckState.Checked if is_good else Qt.CheckState.Unchecked)

            # ID item (column 1)
            id_item = QTableWidgetItem(str(trace_id))
            id_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            self._table_widget.setItem(row, 0, check_item)
            self._table_widget.setItem(row, 1, id_item)
        self._table_widget.blockSignals(False)

        # Collect initially checked traces and plot them
        initially_checked = []
        for row in range(self._table_widget.rowCount()):
            check_item = self._table_widget.item(row, 0)
            id_item = self._table_widget.item(row, 1)
            if check_item and id_item and check_item.checkState() == Qt.CheckState.Checked:
                initially_checked.append(id_item.text())

        if initially_checked:
            self._plot_selected_traces(initially_checked)
            self.selection_changed.emit(initially_checked)

        # Enable the viewer if there are traces
        self.setEnabled(len(self._trace_ids) > 0)
        # Enable save button only if we have a CSV source path
        self._save_button.setEnabled(len(self._trace_ids) > 0 and self._traces_csv_path is not None)

    def set_trace_data(self, trace_ids: list[str], frames: np.ndarray,
                       feature_series: dict[str, dict[str, np.ndarray]],
                       good_status: dict[str, bool] | None = None) -> None:
        """Populate both the selection list and the underlying time-series data.

        Args:
            trace_ids: Identifiers to show in the UI (order respected)
            frames: 1D array of frame indices (x-axis)
            feature_series: Mapping of feature_name -> {trace_id -> series}
            good_status: Optional dict mapping trace_id to good/bad status
        """
        # Clear existing data
        self._feature_series.clear()
        self._available_features.clear()

        self._frames = np.array(frames, dtype=float)

        # Store feature series
        self._feature_series = {
            feat: {str(k): np.asarray(v, dtype=float) for k, v in series.items()}
            for feat, series in feature_series.items()
        }
        self._available_features = list(feature_series.keys())

        # Update dropdown based on available features
        self._update_feature_dropdown()

        self.set_traces([str(tid) for tid in trace_ids], good_status)

    def set_traces_csv_path(self, csv_path: Path | None) -> None:
        """Provide the source CSV path used to populate this viewer.

        Controls enabling of the Save button.
        """
        self._traces_csv_path = csv_path
        self._save_button.setEnabled(self._traces_csv_path is not None and len(self._trace_ids) > 0)

    def check_all(self) -> None:
        """Check all trace items, update plot once, and emit selection change once."""
        if self._table_widget.rowCount() == 0:
            return
        # Avoid per-item signal emissions; we'll emit once at the end
        self._table_widget.blockSignals(True)
        for row in range(self._table_widget.rowCount()):
            item = self._table_widget.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked)
        self._table_widget.blockSignals(False)

        selected = [self._table_widget.item(row, 1).text() for row in range(self._table_widget.rowCount())]
        self._plot_selected_traces(selected)
        self.selection_changed.emit(selected)

    def uncheck_all(self) -> None:
        """Uncheck all trace items, clear plot, and emit selection change once."""
        if self._table_widget.rowCount() == 0:
            return
        self._table_widget.blockSignals(True)
        for row in range(self._table_widget.rowCount()):
            item = self._table_widget.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._table_widget.blockSignals(False)

        self._active_trace_id = None
        self._plot_selected_traces([])
        self.selection_changed.emit([])

    # ---- Internal handlers ----
    def _on_item_changed(self, item) -> None:
        """Emit selection_changed with the list of checked trace IDs."""
        # If it's a checkbox item that changed, update good_status tracking
        if item.column() == 0:
            row = item.row()
            id_item = self._table_widget.item(row, 1)
            if id_item:
                is_checked = item.checkState() == Qt.CheckState.Checked
                # Update internal good_status tracking
                self._good_status[id_item.text()] = is_checked

        selected: list[str] = []
        for row in range(self._table_widget.rowCount()):
            check_item = self._table_widget.item(row, 0)
            id_item = self._table_widget.item(row, 1)
            if check_item is not None and check_item.checkState() == Qt.CheckState.Checked and id_item is not None:
                selected.append(id_item.text())
        # Update local plot with currently selected traces (using mock/loaded data)
        self._plot_selected_traces(selected)
        # Emit outward so image viewer overlay can also react when wired
        self.selection_changed.emit(selected)
        # No dynamic header icon updates needed

    def _on_cell_clicked(self, row: int, column: int) -> None:
        """Handle clicks on the Trace ID column. Only act if the trace is already checked."""
        if column != 1:
            return
        id_item = self._table_widget.item(row, 1)
        if id_item is None:
            return
        # Do nothing if the trace is not checked
        check_item = self._table_widget.item(row, 0)
        if check_item is None or check_item.checkState() != Qt.CheckState.Checked:
            return

        trace_id = id_item.text()
        self._active_trace_id = trace_id
        # Replot to apply highlight color
        selected: list[str] = []
        for r in range(self._table_widget.rowCount()):
            citem = self._table_widget.item(r, 0)
            iid = self._table_widget.item(r, 1)
            if citem is not None and citem.checkState() == Qt.CheckState.Checked and iid is not None:
                selected.append(iid.text())
        self._plot_selected_traces(selected)
        # Notify listeners (e.g., image viewer) of the active trace change
        self.active_trace_changed.emit(trace_id)



    # ---- Internal plotting/data helpers ----
    def _on_header_section_clicked(self, section: int) -> None:
        """Toggle check all/none when checkbox column header is clicked."""
        if section != 0:
            return
        # Determine if any row is unchecked; if so, check all, else uncheck all
        any_unchecked = False
        for row in range(self._table_widget.rowCount()):
            item = self._table_widget.item(row, 0)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                any_unchecked = True
                break
        if any_unchecked:
            self.check_all()
        else:
            self.uncheck_all()

    def _plot_selected_traces(self, selected_ids: list[str]) -> None:
        """Plot the selected traces by their identifiers."""
        if not self._current_trace_type or not self._axes:
            return

        # Get current feature's data
        series_dict = self._feature_series.get(self._current_trace_type, {})

        # Format display name
        display_name = self._current_trace_type.replace('_', ' ').title()

        # Clear and setup axes
        self._axes.cla()
        self._axes.set_xlabel("Frame")
        self._axes.set_ylabel(display_name)
        self._axes.grid(True, linestyle=":", linewidth=0.5)

        if not selected_ids or self._frames.size == 0:
            self._canvas.draw_idle()
            return

        for trace_id in selected_ids:
            series = series_dict.get(trace_id)
            if series is None:
                # Skip missing data
                continue
            is_active = self._active_trace_id == trace_id
            color = "red" if is_active else "gray"
            linewidth = 2.0 if is_active else 1.0
            z_order = 3 if is_active else 2
            alpha = 1.0 if is_active else 0.6
            self._axes.plot(
                self._frames,
                series,
                linewidth=linewidth,
                color=color,
                alpha=alpha,
                zorder=z_order,
            )

        self._canvas.draw_idle()

    def _on_feature_changed(self, text: str) -> None:
        """Handle feature dropdown selection change."""
        if not text:
            return

        # Get the actual feature name from dropdown data
        index = self._feature_dropdown.currentIndex()
        if index >= 0:
            self._current_trace_type = self._feature_dropdown.itemData(index)

            # Replot with current selection
            selected: list[str] = []
            for row in range(self._table_widget.rowCount()):
                check_item = self._table_widget.item(row, 0)
                id_item = self._table_widget.item(row, 1)
                if check_item is not None and check_item.checkState() == Qt.CheckState.Checked and id_item is not None:
                    selected.append(id_item.text())
            self._plot_selected_traces(selected)


    # ---- Save handler ----
    def _on_save_clicked(self) -> None:
        if self._traces_csv_path is None:
            QMessageBox.warning(self, "Save Good Labels", "No source CSV available to save.")
            return
        try:
            # Build set of checked IDs
            selected_ids: set[str] = set()
            for row in range(self._table_widget.rowCount()):
                check_item = self._table_widget.item(row, 0)
                id_item = self._table_widget.item(row, 1)
                if check_item is not None and id_item is not None and check_item.checkState() == Qt.CheckState.Checked:
                    selected_ids.add(id_item.text())

            # Load original CSV
            df = pd.read_csv(self._traces_csv_path)
            # Add/overwrite 'good' column based on membership
            df['good'] = df['cell_id'].astype(str).isin(selected_ids)

            # Compute output path so filename ends with 'traces_inspected'
            original_name = self._traces_csv_path.name
            if original_name.endswith("traces_inspected.csv"):
                # If already inspected, overwrite the same file
                output_name = original_name
            elif original_name.endswith("traces.csv"):
                output_name = original_name.replace("traces.csv", "traces_inspected.csv")
            else:
                # For any other CSV file, append _inspected before .csv
                output_name = self._traces_csv_path.stem + "_inspected.csv"
            output_path = self._traces_csv_path.with_name(output_name)
            df.to_csv(output_path, index=False)

            QMessageBox.information(self, "Save Good Labels", f"Saved: {output_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Good Labels", f"Failed to save inspected CSV:\n{e}")
