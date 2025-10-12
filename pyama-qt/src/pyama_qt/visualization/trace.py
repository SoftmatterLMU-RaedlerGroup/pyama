"""Trace viewer panel for displaying and selecting time traces."""

import logging
from pathlib import Path

import pandas as pd
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
    QWidget,
)

from pyama_core.io.processing_csv import (
    get_dataframe,
    extract_cell_quality_dataframe,
    extract_cell_feature_dataframe,
    update_cell_quality,
    write_dataframe,
)
from .models import FeatureData

from ..components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


class TracePanel(QWidget):
    """Panel to plot time traces and allow selection via a checkable table."""

    activeTraceChanged = Signal(str)
    tracePositionsChanged = Signal(dict)
    statusMessage = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.build()
        self.bind()
        # --- State from Models ---
        self._trace_features: dict[str, FeatureData] = {}
        self._good_status: dict[str, bool] = {}
        self._active_trace_id: str | None = None
        self._traces_csv_path: Path | None = None
        self._processing_df: pd.DataFrame | None = None

        # --- UI State ---
        self._trace_ids: list[str] = []
        self._current_page = 0
        self._items_per_page = 10

    def build(self) -> None:
        layout = QVBoxLayout(self)
        plot_group, list_group = self._build_groups()
        layout.addWidget(plot_group, 1)
        layout.addWidget(list_group, 1)

    def bind(self) -> None:
        self._feature_dropdown.currentTextChanged.connect(lambda: self._plot_current_page())
        self._prev_button.clicked.connect(self._on_prev_page)
        self._next_button.clicked.connect(self._on_next_page)
        self._check_all_button.clicked.connect(lambda: self._set_all_good_status(True))
        self._uncheck_all_button.clicked.connect(lambda: self._set_all_good_status(False))
        self._save_button.clicked.connect(self._on_save_clicked)
        self._table_widget.itemChanged.connect(self._on_item_changed)
        self._table_widget.cellClicked.connect(self._on_cell_clicked)
        self._table_widget.keyPressEvent = self._handle_key_press

    # --- Public Slots ---
    def on_fov_data_loaded(self, image_map: dict, traces_path: Path | None):
        self.clear()
        if not traces_path or not traces_path.exists():
            self.statusMessage.emit("No trace data found for this FOV.")
            return
        self._traces_csv_path = traces_path
        self._load_data_from_csv(traces_path)

    # --- Internal Logic ---
    def _load_data_from_csv(self, csv_path: Path):
        inspected_path = csv_path.with_name(f"{csv_path.stem}_inspected{csv_path.suffix}")
        path_to_load = inspected_path if inspected_path.exists() else csv_path
        try:
            self._processing_df = get_dataframe(path_to_load)
            self._extract_quality_and_features()
            self._update_ui_from_data()
            self.statusMessage.emit(f"Loaded {len(self._trace_ids)} traces.")
        except Exception as e:
            logger.error("Failed to load trace data from %s: %s", path_to_load, e)
            self.statusMessage.emit(f"Error loading traces: {e}")

    def _extract_quality_and_features(self):
        if self._processing_df is None: return
        quality_df = extract_cell_quality_dataframe(self._processing_df)
        self._good_status = {str(int(r["cell"])): bool(r["good"]) for _, r in quality_df.iterrows()}

        features_df = extract_cell_feature_dataframe(self._processing_df, list(self._good_status.keys()))
        for trace_id, group in features_df.groupby('cell'):
            str_id = str(int(trace_id))
            time = group['time'].values
            features = {col: group[col].values for col in group.columns if col not in ['cell', 'time']}
            self._trace_features[str_id] = FeatureData(time_points=time, features=features)

    def _update_ui_from_data(self):
        self._trace_ids = sorted(self._trace_features.keys(), key=int)
        self._current_page = 0
        self._update_pagination()
        self._update_feature_dropdown()
        self._populate_table()
        self._plot_current_page()

    def _plot_current_page(self):
        feature = self._feature_dropdown.currentText()
        if not feature or not self._trace_ids:
            self._canvas.clear()
            return

        lines, styles = [], []
        for trace_id in self._visible_trace_ids():
            data = self._trace_features.get(trace_id)
            if data and feature in data.features:
                style = {"color": "gray", "alpha": 0.3}
                if trace_id == self._active_trace_id:
                    style.update({"color": "red", "linewidth": 2, "alpha": 1.0})
                lines.append((data.time_points, data.features[feature]))
                styles.append(style)

        self._canvas.plot_lines(lines, styles, title=f"{feature} over time", x_label="Time", y_label=feature)

    # --- Event Handlers & UI Updates ---
    def _on_cell_clicked(self, row, col):
        trace_id = self._visible_trace_ids()[row]
        self._set_active_trace(trace_id)

    def _set_active_trace(self, trace_id: str | None):
        if self._active_trace_id == trace_id: return
        self._active_trace_id = trace_id
        self._highlight_active_row()
        self._plot_current_page()
        if trace_id:
            self.activeTraceChanged.emit(trace_id)

    def _highlight_active_row(self):
        for r in range(self._table_widget.rowCount()):
            tid = self._table_widget.item(r, 1).text()
            font = self._table_widget.item(r, 1).font()
            font.setBold(tid == self._active_trace_id)
            self._table_widget.item(r, 1).setFont(font)

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            trace_id = self._visible_trace_ids()[item.row()]
            is_good = item.checkState() == Qt.CheckState.Checked
            self._good_status[trace_id] = is_good
            self._plot_current_page()

    def _on_save_clicked(self):
        if self._processing_df is None or self._traces_csv_path is None:
            self.statusMessage.emit("No data to save.")
            return

        updated_quality = pd.DataFrame(self._good_status.items(), columns=['cell', 'good'])
        updated_df = update_cell_quality(self._processing_df, updated_quality)
        save_path = self._traces_csv_path.with_name(f"{self._traces_csv_path.stem}_inspected.csv")
        try:
            write_dataframe(updated_df, save_path)
            self.statusMessage.emit(f"Saved inspected data to {save_path.name}")
        except Exception as e:
            logger.error("Failed to save inspected data: %s", e)
            self.statusMessage.emit(f"Error saving data: {e}")

    def _set_all_good_status(self, is_good: bool):
        for trace_id in self._trace_ids:
            self._good_status[trace_id] = is_good
        self._populate_table()
        self._plot_current_page()

    def _populate_table(self):
        trace_ids = self._visible_trace_ids()
        self._table_widget.blockSignals(True)
        self. _table_widget.setRowCount(len(trace_ids))
        for r, tid in enumerate(trace_ids):
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check_item.setCheckState(Qt.Checked if self._good_status.get(tid, False) else Qt.Unchecked)
            self._table_widget.setItem(r, 0, check_item)
            self._table_widget.setItem(r, 1, QTableWidgetItem(tid))
        self._table_widget.blockSignals(False)
        self._highlight_active_row()

    def _update_pagination(self):
        total_pages = max(1, (len(self._trace_ids) + self._items_per_page - 1) // self._items_per_page)
        self._page_label.setText(f"Page {self._current_page + 1} of {total_pages}")
        self._prev_button.setEnabled(self._current_page > 0)
        self._next_button.setEnabled(self._current_page < total_pages - 1)

    def _on_prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._update_pagination()
            self._populate_table()
            self._plot_current_page()

    def _on_next_page(self):
        total_pages = (len(self._trace_ids) + self._items_per_page - 1) // self._items_per_page
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._update_pagination()
            self._populate_table()
            self._plot_current_page()

    def _update_feature_dropdown(self):
        self._feature_dropdown.blockSignals(True)
        self._feature_dropdown.clear()
        if self._trace_features:
            features = list(next(iter(self._trace_features.values())).features.keys())
            self._feature_dropdown.addItems(features)
        self._feature_dropdown.blockSignals(False)

    def _visible_trace_ids(self) -> list[str]:
        start = self._current_page * self._items_per_page
        return self._trace_ids[start:start + self._items_per_page]

    def clear(self):
        self._trace_features.clear()
        self._good_status.clear()
        self._trace_ids.clear()
        self._active_trace_id = None
        self._traces_csv_path = None
        self._processing_df = None
        self._table_widget.clearContents()
        self._table_widget.setRowCount(0)
        self._canvas.clear()
        self._feature_dropdown.clear()
        self._current_page = 0
        self._update_pagination()

    def _handle_key_press(self, event: QKeyEvent):
        # Basic navigation and selection logic
        QTableWidget.keyPressEvent(self._table_widget, event)

    def _build_groups(self):
        # Simplified build method for brevity
        plot_group = QGroupBox("Traces")
        plot_layout = QVBoxLayout(plot_group)
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Feature:"))
        self._feature_dropdown = QComboBox()
        selector_layout.addWidget(self._feature_dropdown, 1)
        plot_layout.addLayout(selector_layout)
        self._canvas = MplCanvas(self, width=8, height=6, dpi=100)
        plot_layout.addWidget(self._canvas)

        list_group = QGroupBox("Trace Selection")
        list_layout = QVBoxLayout(list_group)
        pagination_layout = QHBoxLayout()
        self._prev_button = QPushButton("Previous")
        self._page_label = QLabel("Page 1 of 1")
        self._next_button = QPushButton("Next")
        pagination_layout.addWidget(self._prev_button)
        pagination_layout.addWidget(self._page_label)
        pagination_layout.addWidget(self._next_button)
        list_layout.addLayout(pagination_layout)
        controls_layout = QHBoxLayout()
        self._check_all_button = QPushButton("Check All")
        self._uncheck_all_button = QPushButton("Uncheck All")
        self._save_button = QPushButton("Save Inspected")
        controls_layout.addWidget(self._check_all_button)
        controls_layout.addWidget(self._uncheck_all_button)
        controls_layout.addWidget(self._save_button)
        list_layout.addLayout(controls_layout)
        self._table_widget = QTableWidget(0, 2)
        self._table_widget.setHorizontalHeaderLabels(["Good", "Trace ID"])
        self._table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table_widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        list_layout.addWidget(self._table_widget)

        return plot_group, list_group