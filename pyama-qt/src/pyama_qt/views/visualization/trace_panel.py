"""Trace viewer panel for displaying and selecting time traces."""

import logging
from pathlib import Path
from typing import Mapping

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

from pyama_qt.models.visualization import FeatureData
from ..base import BasePanel
from ..components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


class TracePanel(BasePanel):
    """Panel to plot time traces and allow selection via a checkable table."""

    active_trace_changed = Signal(str)
    trace_selection_changed = Signal(str)
    good_state_changed = Signal(str, bool)
    save_requested = Signal(dict, object)  # good status map, target path

    def build(self) -> None:
        layout = QVBoxLayout(self)

        plot_group = QGroupBox("Traces")
        plot_layout = QVBoxLayout(plot_group)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Feature:"))
        self._feature_dropdown = QComboBox()
        selector_layout.addWidget(self._feature_dropdown, 1)
        selector_layout.addStretch()
        plot_layout.addLayout(selector_layout)

        self._canvas = MplCanvas(self, width=8, height=6, dpi=100)
        plot_layout.addWidget(self._canvas)
        layout.addWidget(plot_group, 1)

        list_group = QGroupBox("Trace Selection")
        list_layout = QVBoxLayout(list_group)

        pagination_layout = QHBoxLayout()
        self._prev_button = QPushButton("Previous")
        pagination_layout.addWidget(self._prev_button, 1)

        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addWidget(self._page_label, 1)

        self._next_button = QPushButton("Next")
        pagination_layout.addWidget(self._next_button, 1)
        list_layout.addLayout(pagination_layout)

        controls_layout = QHBoxLayout()
        self._check_all_button = QPushButton("Check All")
        controls_layout.addWidget(self._check_all_button, 1)

        self._uncheck_all_button = QPushButton("Uncheck All")
        controls_layout.addWidget(self._uncheck_all_button, 1)

        self._save_button = QPushButton("Save Inspected")
        controls_layout.addWidget(self._save_button, 1)

        controls_layout.addStretch()
        list_layout.addLayout(controls_layout)

        self._table_widget = QTableWidget(0, 2)
        self._table_widget.setHorizontalHeaderLabels(["Good", "Trace ID"])
        self._table_widget.horizontalHeader().setStretchLastSection(True)
        self._table_widget.verticalHeader().setVisible(False)
        self._table_widget.setAlternatingRowColors(True)
        self._table_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._table_widget.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table_widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        list_layout.addWidget(self._table_widget)

        layout.addWidget(list_group, 1)

        self._trace_data: dict[str, FeatureData] = {}
        self._trace_ids: list[str] = []
        self._good_status: dict[str, bool] = {}
        self._available_features: list[str] = []
        self._active_trace_id: str | None = None
        self._traces_csv_path: Path | None = None

        self._current_page = 0
        self._items_per_page = 10
        self._total_pages = 1

    def bind(self) -> None:
        self._feature_dropdown.currentTextChanged.connect(self._on_feature_changed)
        self._prev_button.clicked.connect(self._on_prev_page)
        self._next_button.clicked.connect(self._on_next_page)
        self._check_all_button.clicked.connect(self._check_all)
        self._uncheck_all_button.clicked.connect(self._uncheck_all)
        self._save_button.clicked.connect(self._on_save_clicked)
        self._table_widget.itemChanged.connect(self._on_item_changed)
        self._table_widget.cellClicked.connect(self._on_cell_clicked)
        self._table_widget.keyPressEvent = self._handle_key_press  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Controller-facing API
    # ------------------------------------------------------------------
    def set_trace_dataset(
        self,
        *,
        traces: Mapping[str, FeatureData],
        good_status: Mapping[str, bool],
        features: list[str],
        source_path: Path | None,
    ) -> None:
        self._trace_data = {trace_id: data for trace_id, data in traces.items()}
        self._trace_ids = sorted(self._trace_data.keys())
        self._good_status = {
            trace_id: bool(good_status.get(trace_id, True))
            for trace_id in self._trace_ids
        }
        self._available_features = features or []
        self._traces_csv_path = source_path

        self._current_page = 0
        self._update_pagination_controls()
        self._update_feature_dropdown()
        self._populate_table()
        self._plot_current_page_selected()

    def set_active_trace(self, trace_id: str | None) -> None:
        self._active_trace_id = trace_id
        if trace_id is None:
            return
        # Ensure the trace is visible in the current page
        if trace_id in self._trace_ids:
            index = self._trace_ids.index(trace_id)
            target_page = index // self._items_per_page
            if target_page != self._current_page:
                self._current_page = target_page
                self._update_pagination_controls()
                self._populate_table()
            row = index % self._items_per_page
            self._table_widget.blockSignals(True)
            self._table_widget.setCurrentCell(row, 1)
            self._table_widget.blockSignals(False)
            self._highlight_active_trace()
            self._plot_current_page_selected()

    def update_good_state(self, trace_id: str, is_good: bool) -> None:
        if trace_id not in self._trace_ids:
            return
        self._good_status[trace_id] = is_good
        if trace_id in self._visible_trace_ids():
            row = self._visible_trace_ids().index(trace_id)
            item = self._table_widget.item(row, 0)
            if item:
                self._table_widget.blockSignals(True)
                item.setCheckState(
                    Qt.CheckState.Checked if is_good else Qt.CheckState.Unchecked
                )
                self._table_widget.blockSignals(False)
        self._plot_current_page_selected()

    def clear(self) -> None:
        self._trace_data.clear()
        self._trace_ids.clear()
        self._good_status.clear()
        self._available_features.clear()
        self._traces_csv_path = None
        self._current_page = 0
        self._total_pages = 1
        self._feature_dropdown.clear()
        self._page_label.setText("Page 1 of 1")
        self._table_widget.setRowCount(0)
        self._canvas.clear()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_feature_changed(self, feature_name: str) -> None:
        if feature_name:
            self._plot_current_page_selected()

    def _on_prev_page(self) -> None:
        if self._current_page == 0:
            return
        self._current_page -= 1
        self._update_pagination_controls()
        self._populate_table()
        self._plot_current_page_selected()

    def _on_next_page(self) -> None:
        if self._current_page >= self._total_pages - 1:
            return
        self._current_page += 1
        self._update_pagination_controls()
        self._populate_table()
        self._plot_current_page_selected()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        row = item.row()
        visible_ids = self._visible_trace_ids()
        if row >= len(visible_ids):
            return
        trace_id = visible_ids[row]
        is_good = item.checkState() == Qt.CheckState.Checked
        self._good_status[trace_id] = is_good
        self._plot_current_page_selected()
        self.good_state_changed.emit(trace_id, is_good)
        self.trace_selection_changed.emit(trace_id)

    def _on_cell_clicked(self, row: int, _column: int) -> None:
        visible_ids = self._visible_trace_ids()
        if row >= len(visible_ids):
            return
        trace_id = visible_ids[row]
        self._active_trace_id = trace_id
        self._highlight_active_trace()
        self._plot_current_page_selected()
        self.active_trace_changed.emit(trace_id)
        self.trace_selection_changed.emit(trace_id)

    def _handle_key_press(self, event: QKeyEvent) -> None:
        current_row = self._table_widget.currentRow()
        visible_ids = self._visible_trace_ids()

        if event.key() == Qt.Key.Key_Up:
            if current_row > 0:
                self._table_widget.setCurrentCell(current_row - 1, 1)
                self._on_cell_clicked(current_row - 1, 1)
            elif self._current_page > 0:
                self._current_page -= 1
                self._update_pagination_controls()
                self._populate_table()
                new_ids = self._visible_trace_ids()
                if new_ids:
                    last_row = len(new_ids) - 1
                    self._table_widget.setCurrentCell(last_row, 1)
                    self._on_cell_clicked(last_row, 1)
            event.accept()
            return

        if event.key() == Qt.Key.Key_Down:
            if current_row < len(visible_ids) - 1:
                self._table_widget.setCurrentCell(current_row + 1, 1)
                self._on_cell_clicked(current_row + 1, 1)
            elif self._current_page < self._total_pages - 1:
                self._current_page += 1
                self._update_pagination_controls()
                self._populate_table()
                if self._visible_trace_ids():
                    self._table_widget.setCurrentCell(0, 1)
                    self._on_cell_clicked(0, 1)
            event.accept()
            return

        if event.key() == Qt.Key.Key_Space:
            if 0 <= current_row < len(visible_ids):
                trace_id = visible_ids[current_row]
                new_state = not self._good_status.get(trace_id, True)
                self._good_status[trace_id] = new_state
                checkbox = self._table_widget.item(current_row, 0)
                if checkbox:
                    self._table_widget.blockSignals(True)
                    checkbox.setCheckState(
                        Qt.CheckState.Checked if new_state else Qt.CheckState.Unchecked
                    )
                    self._table_widget.blockSignals(False)
                self._plot_current_page_selected()
                self.good_state_changed.emit(trace_id, new_state)
                self.trace_selection_changed.emit(trace_id)
            event.accept()
            return

        QTableWidget.keyPressEvent(self._table_widget, event)

    def _on_save_clicked(self) -> None:
        if not self._traces_csv_path:
            logger.warning("No trace CSV path set; skipping save")
            return
        self.save_requested.emit(dict(self._good_status), self._traces_csv_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _visible_trace_ids(self) -> list[str]:
        start = self._current_page * self._items_per_page
        end = start + self._items_per_page
        return self._trace_ids[start:end]

    def _update_feature_dropdown(self) -> None:
        self._feature_dropdown.blockSignals(True)
        self._feature_dropdown.clear()
        if self._available_features:
            self._feature_dropdown.addItems(self._available_features)
        else:
            self._feature_dropdown.addItem("No features available")
        self._feature_dropdown.blockSignals(False)

    def _update_pagination_controls(self) -> None:
        total_traces = len(self._trace_ids)
        self._total_pages = max(
            1, (total_traces + self._items_per_page - 1) // self._items_per_page
        )
        self._current_page = max(0, min(self._current_page, self._total_pages - 1))
        self._page_label.setText(
            f"Page {self._current_page + 1} of {self._total_pages}"
        )

    def _populate_table(self) -> None:
        trace_ids = self._visible_trace_ids()
        self._table_widget.blockSignals(True)
        self._table_widget.setRowCount(len(trace_ids))
        for row, trace_id in enumerate(trace_ids):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            checkbox.setCheckState(
                Qt.CheckState.Checked
                if self._good_status.get(trace_id, True)
                else Qt.CheckState.Unchecked
            )
            self._table_widget.setItem(row, 0, checkbox)

            label_item = QTableWidgetItem(trace_id)
            label_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            )
            self._table_widget.setItem(row, 1, label_item)
        self._table_widget.blockSignals(False)

    def _plot_current_page_selected(self) -> None:
        feature = self._feature_dropdown.currentText()
        if not feature or feature == "No features available":
            self._canvas.clear()
            return

        trace_ids = self._visible_trace_ids()
        if not trace_ids:
            self._canvas.clear()
            return

        lines = []
        styles = []
        for trace_id in trace_ids:
            data = self._trace_data.get(trace_id)
            if not data:
                continue
            values = data.features.get(feature)
            if values is None:
                continue
            time_points = data.time_points
            style = {
                "plot_style": "line",
                "color": "gray",
                "alpha": 0.3,
            }
            if trace_id == self._active_trace_id:
                style.update({"color": "tab:red", "linewidth": 2, "alpha": 1.0})
            lines.append((time_points, values))
            styles.append(style)

        if not lines:
            self._canvas.clear()
            return

        self._canvas.plot_lines(
            lines,
            styles,
            title=f"{feature} over time",
            x_label="Time",
            y_label=feature,
        )

    def _highlight_active_trace(self) -> None:
        trace_ids = self._visible_trace_ids()
        for row, trace_id in enumerate(trace_ids):
            item = self._table_widget.item(row, 1)
            if item:
                font = item.font()
                font.setBold(trace_id == self._active_trace_id)
                item.setFont(font)

    def _check_all(self) -> None:
        for trace_id in self._trace_ids:
            if not self._good_status.get(trace_id, True):
                self._good_status[trace_id] = True
                self.good_state_changed.emit(trace_id, True)
        self._populate_table()
        self._plot_current_page_selected()

    def _uncheck_all(self) -> None:
        for trace_id in self._trace_ids:
            if self._good_status.get(trace_id, True):
                self._good_status[trace_id] = False
                self.good_state_changed.emit(trace_id, False)
        self._populate_table()
        self._plot_current_page_selected()
