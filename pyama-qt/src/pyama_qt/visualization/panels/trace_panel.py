"""Trace viewer panel for displaying and selecting time traces."""

from PySide6.QtWidgets import (
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
from PySide6.QtCore import Qt, Signal

from pyama_qt.components import MplCanvas
from pyama_qt.visualization.state import VisualizationState
from pyama_qt.ui import BasePanel
from pyama_core.io.processing_csv import load_processing_csv
import numpy as np


class TracePanel(BasePanel[VisualizationState]):
    """Panel to plot time traces and allow selection via a checkable table."""

    active_trace_changed = Signal(str)
    trace_selection_changed = Signal(str)  # Emitted when trace selection changes

    def build(self) -> None:
        layout = QVBoxLayout(self)

        plot_group = QGroupBox("Traces")
        plot_vbox = QVBoxLayout(plot_group)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Feature:"))
        self._feature_dropdown = QComboBox()
        self._feature_dropdown.currentTextChanged.connect(self._on_feature_changed)
        selector_layout.addWidget(self._feature_dropdown, 1)
        selector_layout.addStretch()
        plot_vbox.addLayout(selector_layout)

        self._canvas = MplCanvas(self, width=8, height=6, dpi=100)
        plot_vbox.addWidget(self._canvas)
        layout.addWidget(plot_group, 1)

        list_group = QGroupBox("Trace Selection")
        list_vbox = QVBoxLayout(list_group)

        # Control buttons
        button_layout = QHBoxLayout()
        self._check_all_button = QPushButton("Check All")
        self._check_all_button.clicked.connect(self._check_all)
        button_layout.addWidget(self._check_all_button)

        self._uncheck_all_button = QPushButton("Uncheck All")
        self._uncheck_all_button.clicked.connect(self._uncheck_all)
        button_layout.addWidget(self._uncheck_all_button)

        self._save_button = QPushButton("Save Labels")
        self._save_button.clicked.connect(self._on_save_clicked)
        self._save_button.setEnabled(False)
        button_layout.addWidget(self._save_button)

        button_layout.addStretch()
        list_vbox.addLayout(button_layout)

        # Table for trace selection
        self._table_widget = QTableWidget(0, 2)
        self._table_widget.setHorizontalHeaderLabels(["Good", "Trace ID"])
        self._table_widget.horizontalHeader().setStretchLastSection(True)
        self._table_widget.verticalHeader().setVisible(False)
        self._table_widget.setAlternatingRowColors(True)
        self._table_widget.itemChanged.connect(self._on_item_changed)
        self._table_widget.cellClicked.connect(self._on_cell_clicked)

        # Make header clickable for check all/none
        header = self._table_widget.horizontalHeader()
        header.sectionClicked.connect(self._on_header_section_clicked)

        list_vbox.addWidget(self._table_widget)
        layout.addWidget(list_group, 1)

        # Initialize state
        self._trace_ids = []
        self._feature_series = {}
        self._available_features = []
        self._active_trace_id = None
        self._frames = np.array([], dtype=float)
        self._traces_csv_path = None
        self._good_status = {}

    def bind(self) -> None:
        # No additional bindings needed for this panel
        pass

    def set_state(self, state: VisualizationState) -> None:
        super().set_state(state)

        if not state:
            return

        # Update trace data if available
        if state.trace_data:
            self._update_trace_data(state.trace_data)

        # Update traces CSV path
        self._traces_csv_path = state.traces_csv_path
        self._save_button.setEnabled(
            self._traces_csv_path is not None and len(self._trace_ids) > 0
        )

        # Update active trace
        if state.active_trace_id != self._active_trace_id:
            self._active_trace_id = state.active_trace_id
            self._highlight_active_trace()

    # Event handlers -------------------------------------------------------
    def _on_feature_changed(self, feature_name: str) -> None:
        """Handle feature selection change."""
        if feature_name and feature_name in self._feature_series:
            selected_ids = self._get_selected_ids()
            self._plot_selected_traces(selected_ids, feature_name)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Handle table item change (checkbox state)."""
        if item.column() == 0:  # Good column
            row = item.row()
            if row < len(self._trace_ids):
                trace_id = self._trace_ids[row]
                is_good = item.checkState() == Qt.CheckState.Checked
                self._good_status[trace_id] = is_good

    def _on_cell_clicked(self, row: int, column: int) -> None:
        """Handle table cell click for trace selection."""
        if row < len(self._trace_ids):
            trace_id = self._trace_ids[row]

            # Set as active trace
            self._active_trace_id = trace_id
            self._highlight_active_trace()

            # Emit signal for other components
            self.active_trace_changed.emit(trace_id)
            self.trace_selection_changed.emit(trace_id)

    def _on_header_section_clicked(self, section: int) -> None:
        """Handle header click for check all/none functionality."""
        if section == 0:  # Good column header
            # Toggle between check all and uncheck all
            checked_count = sum(1 for status in self._good_status.values() if status)
            if checked_count == len(self._trace_ids):
                self._uncheck_all()
            else:
                self._check_all()

    def _on_save_clicked(self) -> None:
        """Handle save labels button click."""
        if not self._traces_csv_path or not self._trace_ids:
            return

        try:
            # Load the original CSV
            df = load_processing_csv(self._traces_csv_path)

            # Update the 'good' column based on current status
            for trace_id in self._trace_ids:
                if trace_id in df.columns:
                    is_good = self._good_status.get(trace_id, True)
                    # Update the 'good' row for this trace
                    if "good" in df.index:
                        df.loc["good", trace_id] = is_good

            # Save back to CSV
            df.to_csv(self._traces_csv_path)

            QMessageBox.information(
                self,
                "Labels Saved",
                f"Updated labels saved to:\n{self._traces_csv_path}",
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Save Error", f"Failed to save labels:\n{str(e)}"
            )

    # Private methods -------------------------------------------------------
    def _update_trace_data(self, trace_data: dict) -> None:
        """Update the panel with new trace data."""
        if not trace_data or not trace_data.get("cell_ids"):
            self.clear()
            return

        # Extract data
        self._trace_ids = [str(cid) for cid in trace_data["cell_ids"]]

        # Update good status
        good_cells = trace_data.get("good_cells", set())
        self._good_status = {
            str(cid): cid in good_cells for cid in trace_data["cell_ids"]
        }

        # Update feature data if available
        if trace_data.get("features"):
            # Create frames axis from first feature
            first_feature = list(trace_data["features"].keys())[0]
            first_cell_data = list(trace_data["features"][first_feature].values())[0]
            self._frames = np.arange(len(first_cell_data))

            # Convert feature data
            self._feature_series = {}
            for feature_name, cell_data in trace_data["features"].items():
                self._feature_series[feature_name] = {
                    str(k): np.array(v) for k, v in cell_data.items()
                }

            self._available_features = list(self._feature_series.keys())
        else:
            self._feature_series = {}
            self._available_features = []
            self._frames = np.array([])

        # Update UI
        self._update_feature_dropdown()
        self._populate_table()

    def _update_feature_dropdown(self) -> None:
        """Update the feature dropdown with available features."""
        self._feature_dropdown.blockSignals(True)
        self._feature_dropdown.clear()

        if self._available_features:
            self._feature_dropdown.addItems(self._available_features)
            self._feature_dropdown.setEnabled(True)
            # Select first feature by default
            if self._available_features:
                self._feature_dropdown.setCurrentText(self._available_features[0])
        else:
            self._feature_dropdown.addItem("No features available")
            self._feature_dropdown.setEnabled(False)

        self._feature_dropdown.blockSignals(False)

    def _populate_table(self) -> None:
        """Populate the table with trace IDs and good status."""
        self._table_widget.blockSignals(True)
        self._table_widget.setRowCount(len(self._trace_ids))

        for row, trace_id in enumerate(self._trace_ids):
            # Good status checkbox
            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            is_good = self._good_status.get(trace_id, True)
            check_item.setCheckState(
                Qt.CheckState.Checked if is_good else Qt.CheckState.Unchecked
            )
            self._table_widget.setItem(row, 0, check_item)

            # Trace ID
            id_item = QTableWidgetItem(trace_id)
            id_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table_widget.setItem(row, 1, id_item)

        self._table_widget.blockSignals(False)

    def _highlight_active_trace(self) -> None:
        """Highlight the active trace in the table."""
        for row in range(self._table_widget.rowCount()):
            id_item = self._table_widget.item(row, 1)
            if id_item:
                if id_item.text() == self._active_trace_id:
                    self._table_widget.selectRow(row)
                    break

    def _get_selected_ids(self) -> list[str]:
        """Get list of selected (good) trace IDs."""
        selected = []
        for trace_id in self._trace_ids:
            if self._good_status.get(trace_id, True):
                selected.append(trace_id)
        return selected

    def _plot_selected_traces(
        self, selected_ids: list[str], feature_name: str | None = None
    ) -> None:
        """Plot the selected traces for the given feature."""
        if not self._canvas or not selected_ids:
            return

        if feature_name is None:
            feature_name = self._feature_dropdown.currentText()

        if not feature_name or feature_name not in self._feature_series:
            return

        self._canvas.axes.clear()

        feature_data = self._feature_series[feature_name]

        # Plot each selected trace
        for trace_id in selected_ids:
            if trace_id in feature_data:
                trace_values = feature_data[trace_id]
                if len(trace_values) > 0:
                    # Highlight active trace differently
                    if trace_id == self._active_trace_id:
                        self._canvas.axes.plot(
                            self._frames,
                            trace_values,
                            linewidth=3,
                            alpha=0.8,
                            label=f"Trace {trace_id}",
                        )
                    else:
                        self._canvas.axes.plot(
                            self._frames,
                            trace_values,
                            alpha=0.6,
                            label=f"Trace {trace_id}",
                        )

        self._canvas.axes.set_xlabel("Frame")
        self._canvas.axes.set_ylabel(feature_name)
        self._canvas.axes.set_title(f"{feature_name} - {len(selected_ids)} traces")

        # Only show legend if not too many traces
        if len(selected_ids) <= 10:
            self._canvas.axes.legend()

        self._canvas.draw()

    def _check_all(self) -> None:
        """Check all traces as good."""
        if self._table_widget.rowCount() == 0:
            return

        self._table_widget.blockSignals(True)
        for row in range(self._table_widget.rowCount()):
            item = self._table_widget.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked)
                if row < len(self._trace_ids):
                    self._good_status[self._trace_ids[row]] = True
        self._table_widget.blockSignals(False)

        # Update plot
        selected_ids = self._get_selected_ids()
        self._plot_selected_traces(selected_ids)

    def _uncheck_all(self) -> None:
        """Uncheck all traces."""
        if self._table_widget.rowCount() == 0:
            return

        self._table_widget.blockSignals(True)
        for row in range(self._table_widget.rowCount()):
            item = self._table_widget.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)
                if row < len(self._trace_ids):
                    self._good_status[self._trace_ids[row]] = False
        self._table_widget.blockSignals(False)

        # Clear plot
        if self._canvas:
            self._canvas.axes.clear()
            self._canvas.draw()

    def clear(self) -> None:
        """Clear all trace data and UI."""
        self._trace_ids.clear()
        self._active_trace_id = None
        self._feature_series.clear()
        self._available_features.clear()
        self._good_status.clear()
        self._frames = np.array([])

        if hasattr(self, "_table_widget"):
            self._table_widget.setRowCount(0)

        if hasattr(self, "_feature_dropdown"):
            self._feature_dropdown.clear()
            self._feature_dropdown.addItem("No features available")
            self._feature_dropdown.setEnabled(False)

        if hasattr(self, "_canvas"):
            self._canvas.axes.clear()
            self._canvas.draw()
