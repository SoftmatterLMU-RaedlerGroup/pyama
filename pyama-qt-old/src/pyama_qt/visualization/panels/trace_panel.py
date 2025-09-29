"""Trace viewer panel for displaying and selecting time traces."""

import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pyama_qt.components import MplCanvas
from pyama_qt.ui import ModelBoundPanel
from pyama_qt.visualization.models import (
    ProjectModel,
    TraceFeatureModel,
    TraceSelectionModel,
    TraceTableModel,
)

logger = logging.getLogger(__name__)


class TracePanel(ModelBoundPanel):
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

        # Pagination controls
        pagination_layout = QHBoxLayout()
        self._prev_button = QPushButton("Previous")
        self._prev_button.clicked.connect(self._on_prev_page)
        pagination_layout.addWidget(self._prev_button, 1)

        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addWidget(self._page_label, 1)

        self._next_button = QPushButton("Next")
        self._next_button.clicked.connect(self._on_next_page)
        pagination_layout.addWidget(self._next_button, 1)

        list_vbox.addLayout(pagination_layout)

        # Control buttons
        button_layout = QHBoxLayout()
        self._check_all_button = QPushButton("Check All")
        self._check_all_button.clicked.connect(self._check_all)
        button_layout.addWidget(self._check_all_button, 1)

        self._uncheck_all_button = QPushButton("Uncheck All")
        self._uncheck_all_button.clicked.connect(self._uncheck_all)
        button_layout.addWidget(self._uncheck_all_button, 1)

        self._save_button = QPushButton("Save Inspected")
        self._save_button.clicked.connect(self._on_save_clicked)
        # Widget enable/disable state is left to external controllers.
        button_layout.addWidget(self._save_button, 1)

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

        # Enable keyboard navigation
        self._table_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._table_widget.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table_widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table_widget.keyPressEvent = self._handle_key_press

        list_vbox.addWidget(self._table_widget)
        layout.addWidget(list_group, 1)

        # Initialize state
        self._trace_ids: list[str] = []
        self._available_features: list[str] = []
        self._active_trace_id: str | None = None
        self._traces_csv_path: Path | None = None
        self._good_status: dict[str, bool] = {}
        self._table_model: TraceTableModel | None = None
        self._feature_model: TraceFeatureModel | None = None
        self._selection_model: TraceSelectionModel | None = None
        self._project_model: ProjectModel | None = None

        # Pagination state
        self._current_page = 0
        self._items_per_page = 10
        self._total_pages = 0

    def bind(self) -> None:
        # No additional bindings needed for this panel
        pass

    def set_models(
        self,
        table_model: TraceTableModel,
        feature_model: TraceFeatureModel,
        selection_model: TraceSelectionModel,
        project_model: ProjectModel | None = None,
    ) -> None:
        self._table_model = table_model
        self._feature_model = feature_model
        self._selection_model = selection_model
        self._project_model = project_model

        table_model.tracesReset.connect(self._sync_from_model)
        table_model.goodStateChanged.connect(self._on_good_state_changed)
        feature_model.availableFeaturesChanged.connect(self._update_feature_dropdown)
        feature_model.featureDataChanged.connect(self._on_feature_data_changed)
        selection_model.activeTraceChanged.connect(self._on_active_trace_changed)

        self._sync_from_model()

    def set_trace_csv_path(self, path: Path | None) -> None:
        """Set the path to the trace CSV file for saving, preferring inspected files."""
        if path is None:
            self._traces_csv_path = None
            self._loaded_csv_path = None
            return

        # Check if an inspected version exists and prefer it
        inspected_path = path.with_name(path.stem + "_inspected" + path.suffix)
        if inspected_path.exists():
            self._loaded_csv_path = inspected_path
            self._traces_csv_path = inspected_path  # Save back to the same file
        else:
            self._loaded_csv_path = path
            self._traces_csv_path = path

    # Event handlers -------------------------------------------------------
    def _on_feature_changed(self, feature_name: str) -> None:
        """Handle feature selection change."""
        if feature_name and feature_name != "No features available":
            # Plot only the selected traces from the current page
            self._plot_current_page_selected()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Handle table item change (checkbox state)."""
        if item.column() == 0:  # Good column
            row = item.row()
            current_page_traces = self._get_current_page_traces()
            if row < len(current_page_traces):
                trace_id = current_page_traces[row]
                is_good = item.checkState() == Qt.CheckState.Checked
                self._good_status[trace_id] = is_good
                if self._table_model:
                    self._table_model.set_good_state(trace_id, is_good)
                self._plot_current_page_selected()
                self.trace_selection_changed.emit(trace_id)

    def _on_cell_clicked(self, row: int, column: int) -> None:
        """Handle table cell click for trace selection."""
        current_page_traces = self._get_current_page_traces()
        if row < len(current_page_traces):
            trace_id = current_page_traces[row]

            # Set as active trace
            if self._selection_model:
                self._selection_model.set_active_trace(trace_id)
            self._active_trace_id = trace_id
            self._highlight_active_trace()

            # Update plot to show the active trace highlighted
            self._plot_current_page_selected()

            # Emit signal for other components
            self.active_trace_changed.emit(trace_id)
            self.trace_selection_changed.emit(trace_id)

    def _on_prev_page(self) -> None:
        """Handle previous page button click."""
        if self._current_page > 0:
            self._current_page -= 1
            self._update_pagination_controls()
            self._populate_table()
            self._plot_current_page_selected()

    def _on_next_page(self) -> None:
        """Handle next page button click."""
        if self._current_page < self._total_pages - 1:
            self._current_page += 1
            self._update_pagination_controls()
            self._populate_table()
            self._plot_current_page_selected()

    def _handle_key_press(self, event: QKeyEvent) -> None:
        """Handle keyboard navigation and actions."""
        current_row = self._table_widget.currentRow()
        current_page_traces = self._get_current_page_traces()

        if event.key() == Qt.Key.Key_Up:
            if current_row > 0:
                # Move up within current page
                self._table_widget.setCurrentCell(
                    current_row - 1, self._table_widget.currentColumn()
                )
                self._on_cell_clicked(
                    current_row - 1, self._table_widget.currentColumn()
                )
            elif self._current_page > 0:
                # Move to previous page, last row
                self._current_page -= 1
                self._update_pagination_controls()
                self._populate_table()
                new_page_traces = self._get_current_page_traces()
                if new_page_traces:
                    last_row = len(new_page_traces) - 1
                    self._table_widget.setCurrentCell(
                        last_row, self._table_widget.currentColumn()
                    )
                    self._on_cell_clicked(last_row, self._table_widget.currentColumn())
                self._plot_current_page_selected()
            event.accept()

        elif event.key() == Qt.Key.Key_Down:
            if current_row < len(current_page_traces) - 1:
                # Move down within current page
                self._table_widget.setCurrentCell(
                    current_row + 1, self._table_widget.currentColumn()
                )
                self._on_cell_clicked(
                    current_row + 1, self._table_widget.currentColumn()
                )
            elif self._current_page < self._total_pages - 1:
                # Move to next page, first row
                self._current_page += 1
                self._update_pagination_controls()
                self._populate_table()
                self._table_widget.setCurrentCell(0, self._table_widget.currentColumn())
                self._on_cell_clicked(0, self._table_widget.currentColumn())
                self._plot_current_page_selected()
            event.accept()

        elif event.key() == Qt.Key.Key_Space:
            if 0 <= current_row < len(current_page_traces):
                # Toggle good status for current trace
                trace_id = current_page_traces[current_row]
                current_status = self._good_status.get(trace_id, True)
                new_state = not current_status
                self._good_status[trace_id] = new_state
                if self._table_model:
                    self._table_model.set_good_state(trace_id, new_state)
                checkbox_item = self._table_widget.item(current_row, 0)
                if checkbox_item:
                    checkbox_item.setCheckState(
                        Qt.CheckState.Checked if new_state else Qt.CheckState.Unchecked
                    )
                self._plot_current_page_selected()
                self.trace_selection_changed.emit(trace_id)
            event.accept()

        else:
            # Let the table widget handle other keys normally
            QTableWidget.keyPressEvent(self._table_widget, event)

    def _on_save_clicked(self) -> None:
        """Handle save labels button click."""
        if (
            not self._traces_csv_path
            or not self._loaded_csv_path
            or not self._trace_ids
        ):
            return

        try:
            # Use the table model's save functionality directly
            if self._table_model:
                success = self._table_model.save_inspected_data(self._traces_csv_path)
                if success:
                    logger.info(
                        f"Updated labels saved to: {self._loaded_csv_path.name}"
                    )
                else:
                    logger.error("Failed to save inspected data")
            else:
                logger.error("No table model available for saving")

        except Exception as e:
            logger.error(f"Failed to save labels: {str(e)}")

    # Private methods -------------------------------------------------------
    def _sync_from_model(self) -> None:
        """Sync the panel's state from the models."""
        if not self._table_model:
            return

        records = self._table_model.traces()
        self._trace_ids = [str(r.cell_id) for r in records]
        self._good_status = {str(r.cell_id): r.good for r in records}
        self._active_trace_id = (
            self._selection_model.active_trace() if self._selection_model else None
        )

        # Update feature data if available
        if self._feature_model:
            self._available_features = self._feature_model.available_features()
        else:
            self._available_features = []

        # Update pagination
        self._update_pagination_state()

        # Update UI
        self._update_feature_dropdown()
        self._populate_table()

        # Auto-plot the first few traces with the first feature
        if self._available_features and self._trace_ids:
            # Auto-check the first few traces (up to 5)
            traces_to_check = min(5, len(self._trace_ids))
            for i in range(traces_to_check):
                row = i % self._items_per_page  # Handle pagination
                if row < self._table_widget.rowCount():
                    item = self._table_widget.item(row, 0)  # Good column
                    if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                        item.setCheckState(Qt.CheckState.Checked)

            # Plot with the first feature
            self._plot_current_page_selected()

    def _on_good_state_changed(self, trace_id: str, is_good: bool) -> None:
        """Handle good state change from the model."""
        self._good_status[trace_id] = is_good
        self._plot_current_page_selected()
        self.trace_selection_changed.emit(trace_id)

    def _on_feature_data_changed(self, trace_features: dict) -> None:
        """Handle feature data change from the model."""
        if trace_features and self._feature_model:
            self._available_features = self._feature_model.available_features()
            self._update_feature_dropdown()
            self._plot_current_page_selected()

    def _on_active_trace_changed(self, trace_id: str) -> None:
        """Handle active trace change from the model."""
        self._active_trace_id = str(trace_id)
        self._highlight_active_trace()

        # Update plot if the active trace is on the current page
        current_page_traces = self._get_current_page_traces()
        if trace_id in current_page_traces:
            self._plot_current_page_selected()

    def _update_feature_dropdown(self) -> None:
        """Update the feature dropdown with available features."""
        self._feature_dropdown.blockSignals(True)
        self._feature_dropdown.clear()

        if self._available_features:
            self._feature_dropdown.addItems(self._available_features)
            # Do not toggle enabled/disabled state here; controllers manage it.
            if self._available_features:
                self._feature_dropdown.setCurrentText(self._available_features[0])
        else:
            self._feature_dropdown.addItem("No features available")
            # controllers may decide to disable the dropdown if desired

        self._feature_dropdown.blockSignals(False)

    def _update_pagination_state(self) -> None:
        """Update pagination state based on current trace count."""
        if not self._trace_ids:
            self._total_pages = 0
            self._current_page = 0
        else:
            self._total_pages = (
                len(self._trace_ids) + self._items_per_page - 1
            ) // self._items_per_page
            self._current_page = min(self._current_page, self._total_pages - 1)
            if self._current_page < 0:
                self._current_page = 0

        self._update_pagination_controls()

    def _update_pagination_controls(self) -> None:
        """Update pagination control states and labels."""
        if self._total_pages <= 1:
            self._prev_button.setEnabled(False)
            self._next_button.setEnabled(False)
            self._page_label.setText("Page 1 of 1")
        else:
            self._prev_button.setEnabled(self._current_page > 0)
            self._next_button.setEnabled(self._current_page < self._total_pages - 1)
            self._page_label.setText(
                f"Page {self._current_page + 1} of {self._total_pages}"
            )

    def _get_current_page_traces(self) -> list[str]:
        """Get trace IDs for the current page."""
        if not self._trace_ids:
            return []

        start_idx = self._current_page * self._items_per_page
        end_idx = min(start_idx + self._items_per_page, len(self._trace_ids))
        return self._trace_ids[start_idx:end_idx]

    def _populate_table(self) -> None:
        """Populate the table with trace IDs and good status for current page."""
        current_page_traces = self._get_current_page_traces()
        self._table_widget.blockSignals(True)
        self._table_widget.setRowCount(len(current_page_traces))

        for row, trace_id in enumerate(current_page_traces):
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
                    self._table_widget.setCurrentCell(row, 1)
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

        if not feature_name or not self._feature_model:
            return

        if feature_name not in self._available_features:
            return

        self._canvas.axes.clear()

        # Get time units from project model
        time_units = None
        if self._project_model:
            time_units = self._project_model.time_units()

        # Default x-axis label
        x_label = f"Time ({time_units})" if time_units else "Time"

        plot_count = 0
        # Plot each selected trace
        for trace_id in selected_ids:
            if self._feature_model:
                trace_values = self._feature_model.get_feature_values(trace_id, feature_name)
                time_values = self._feature_model.get_time_points(trace_id)

                if trace_values is not None and len(trace_values) > 0:
                    plot_count += 1

                    # Use time data if available, otherwise fall back to frame indices
                    if time_values is not None and len(time_values) == len(trace_values):
                        x_data = time_values
                    else:
                        x_data = np.arange(len(trace_values))
                        x_label = "Frame"

                    # Highlight active trace differently
                    if trace_id == self._active_trace_id:
                        self._canvas.axes.plot(
                            x_data,
                            trace_values,
                            color="red",
                            linewidth=3,
                            alpha=0.8,
                        )
                    else:
                        self._canvas.axes.plot(
                            x_data,
                            trace_values,
                            color="gray",
                            alpha=0.6,
                        )

        self._canvas.axes.set_xlabel(x_label)
        self._canvas.axes.set_ylabel(feature_name)
        self._canvas.axes.set_title(
            f"{feature_name} - {len(selected_ids)} traces (page {self._current_page + 1}/{self._total_pages})"
        )

        self._canvas.draw()

    def _plot_current_page_selected(self) -> None:
        """Plot selected traces from the current page."""
        current_page_traces = self._get_current_page_traces()
        selected_from_page = [
            trace_id
            for trace_id in current_page_traces
            if self._good_status.get(trace_id, True)
        ]

        feature_name = self._feature_dropdown.currentText()
        if feature_name and feature_name != "No features available":
            self._plot_selected_traces(selected_from_page, feature_name)

    def _check_all(self) -> None:
        """Check all traces on current page as good."""
        if self._table_widget.rowCount() == 0:
            return

        current_page_traces = self._get_current_page_traces()
        self._table_widget.blockSignals(True)
        for row in range(self._table_widget.rowCount()):
            item = self._table_widget.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked)
                if row < len(current_page_traces):
                    trace_id = current_page_traces[row]
                    self._good_status[trace_id] = True
                    if self._table_model:
                        self._table_model.set_good_state(trace_id, True)
        self._table_widget.blockSignals(False)
        self._plot_current_page_selected()
        if current_page_traces:
            self.trace_selection_changed.emit(current_page_traces[-1])

    def _uncheck_all(self) -> None:
        """Uncheck all traces on current page."""
        if self._table_widget.rowCount() == 0:
            return

        current_page_traces = self._get_current_page_traces()
        self._table_widget.blockSignals(True)
        for row in range(self._table_widget.rowCount()):
            item = self._table_widget.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)
                if row < len(current_page_traces):
                    trace_id = current_page_traces[row]
                    self._good_status[trace_id] = False
                    if self._table_model:
                        self._table_model.set_good_state(trace_id, False)
        self._table_widget.blockSignals(False)
        self._plot_current_page_selected()
        if current_page_traces:
            self.trace_selection_changed.emit(current_page_traces[-1])

    def clear(self) -> None:
        """Clear all trace data and UI."""
        self._trace_ids.clear()
        self._active_trace_id = None
        self._available_features.clear()
        self._good_status.clear()

        # Reset pagination
        self._current_page = 0
        self._total_pages = 0

        if hasattr(self, "_table_widget"):
            self._table_widget.setRowCount(0)

        if hasattr(self, "_feature_dropdown"):
            self._feature_dropdown.clear()
            self._feature_dropdown.addItem("No features available")
            # controllers may decide whether the dropdown should be interactive

        if hasattr(self, "_canvas"):
            self._canvas.axes.clear()
            self._canvas.draw()

        # Update pagination controls
        if hasattr(self, "_prev_button"):
            self._update_pagination_controls()

  