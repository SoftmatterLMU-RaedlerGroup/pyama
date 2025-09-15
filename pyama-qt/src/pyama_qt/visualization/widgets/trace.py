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
from PySide6.QtCore import Qt, Signal

from pyama_qt.widgets.mpl_canvas import MplCanvas
from pyama_core.io.processing_csv import ProcessingCSVLoader
import numpy as np
from pathlib import Path


class TracePanel(QWidget):
    """Widget to plot time traces and allow selection via a checkable table."""

    selection_changed = Signal(list)
    active_trace_changed = Signal(str)

    def __init__(self):
        super().__init__()

        self._trace_ids: list[str] = []
        self._feature_series: dict[str, dict[str, np.ndarray]] = {}
        self._available_features: list[str] = []
        self._active_trace_id: str | None = None
        self._frames: np.ndarray = np.array([], dtype=float)
        self._traces_csv_path: Path | None = None
        self._current_trace_type: str | None = None
        self._good_status: dict[str, bool] = {}

        self._canvas: MplCanvas | None = None
        self._feature_dropdown: QComboBox | None = None

        self._setup_ui()
        self.setEnabled(False)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

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
        self._table_widget.setColumnWidth(0, 36)
        header_hint_item = QTableWidgetItem("☐")
        header_hint_item.setToolTip("Click to toggle check all/none")
        header_hint_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table_widget.setHorizontalHeaderItem(0, header_hint_item)
        list_vbox.addWidget(self._table_widget)

        self._save_button = QPushButton("Save 'good' traces")
        self._save_button.setToolTip(
            "Write a new CSV with a 'good' column based on checked rows"
        )
        self._save_button.clicked.connect(self._on_save_clicked)
        self._save_button.setEnabled(False)
        list_vbox.addWidget(self._save_button)
        layout.addWidget(list_group, 1)

    def _update_feature_dropdown(self) -> None:
        self._feature_dropdown.blockSignals(True)
        self._feature_dropdown.clear()

        for feature_name in self._available_features:
            display_name = feature_name.replace("_", " ").title()
            self._feature_dropdown.addItem(display_name, feature_name)

        if self._available_features:
            self._feature_dropdown.setCurrentIndex(0)
            self._current_trace_type = self._available_features[0]

        self._feature_dropdown.blockSignals(False)

    def clear(self) -> None:
        self._trace_ids.clear()
        self._active_trace_id = None
        self._feature_series.clear()
        self._available_features.clear()
        self._good_status.clear()

        if hasattr(self, "_table_widget"):
            self._table_widget.blockSignals(True)
            self._table_widget.setRowCount(0)
            self._table_widget.blockSignals(False)

        if self._canvas:
            self._canvas.clear(clear_figure=True)

        if self._feature_dropdown:
            self._feature_dropdown.clear()

        self.setEnabled(False)

    def set_traces(
        self,
        trace_ids: list[str],
        good_status: dict[str, bool] | None = None,
    ) -> None:
        self._trace_ids = list(trace_ids)
        self._active_trace_id = None

        if good_status:
            self._good_status = good_status.copy()
        else:
            self._good_status = {tid: True for tid in self._trace_ids}

        self._table_widget.blockSignals(True)
        self._table_widget.setRowCount(len(self._trace_ids))
        for row, trace_id in enumerate(self._trace_ids):
            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            is_good = self._good_status.get(trace_id, True)
            check_item.setCheckState(
                Qt.CheckState.Checked if is_good else Qt.CheckState.Unchecked
            )

            id_item = QTableWidgetItem(str(trace_id))
            id_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            self._table_widget.setItem(row, 0, check_item)
            self._table_widget.setItem(row, 1, id_item)
        self._table_widget.blockSignals(False)

        initially_checked = []
        for row in range(self._table_widget.rowCount()):
            check_item = self._table_widget.item(row, 0)
            id_item = self._table_widget.item(row, 1)
            if (
                check_item
                and id_item
                and check_item.checkState() == Qt.CheckState.Checked
            ):
                initially_checked.append(id_item.text())

        if initially_checked:
            self._plot_selected_traces(initially_checked)
            self.selection_changed.emit(initially_checked)

        self.setEnabled(len(self._trace_ids) > 0)
        self._save_button.setEnabled(
            len(self._trace_ids) > 0 and self._traces_csv_path is not None
        )

    def set_trace_data(
        self,
        trace_ids: list[str],
        frames: np.ndarray,
        feature_series: dict[str, dict[str, np.ndarray]],
        good_status: dict[str, bool] | None = None,
    ) -> None:
        self._feature_series.clear()
        self._available_features.clear()

        self._frames = np.array(frames, dtype=float)

        self._feature_series = {
            feat: {str(k): np.asarray(v, dtype=float) for k, v in series.items()}
            for feat, series in feature_series.items()
        }
        self._available_features = list(feature_series.keys())

        self._update_feature_dropdown()

        self.set_traces([str(tid) for tid in trace_ids], good_status)

    def set_traces_csv_path(self, csv_path: Path | None) -> None:
        self._traces_csv_path = csv_path
        self._save_button.setEnabled(
            self._traces_csv_path is not None and len(self._trace_ids) > 0
        )

    def check_all(self) -> None:
        if self._table_widget.rowCount() == 0:
            return
        self._table_widget.blockSignals(True)
        for row in range(self._table_widget.rowCount()):
            item = self._table_widget.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked)
        self._table_widget.blockSignals(False)

        selected = [
            self._table_widget.item(row, 1).text()
            for row in range(self._table_widget.rowCount())
        ]
        self._plot_selected_traces(selected)
        self.selection_changed.emit(selected)

    def uncheck_all(self) -> None:
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

    def _on_item_changed(self, item) -> None:
        if item.column() == 0:
            row = item.row()
            id_item = self._table_widget.item(row, 1)
            if id_item:
                is_checked = item.checkState() == Qt.CheckState.Checked
                self._good_status[id_item.text()] = is_checked

        selected: list[str] = []
        for row in range(self._table_widget.rowCount()):
            check_item = self._table_widget.item(row, 0)
            id_item = self._table_widget.item(row, 1)
            if (
                check_item is not None
                and check_item.checkState() == Qt.CheckState.Checked
                and id_item is not None
            ):
                selected.append(id_item.text())
        self._plot_selected_traces(selected)
        self.selection_changed.emit(selected)

    def _on_cell_clicked(self, row: int, column: int) -> None:
        if column != 1:
            return
        id_item = self._table_widget.item(row, 1)
        if id_item is None:
            return
        check_item = self._table_widget.item(row, 0)
        if check_item is None or check_item.checkState() != Qt.CheckState.Checked:
            return

        trace_id = id_item.text()
        self._active_trace_id = trace_id
        self._plot_selected_traces(self.get_selected_ids())
        self.active_trace_changed.emit(trace_id)

    def get_selected_ids(self) -> list[str]:
        selected: list[str] = []
        for r in range(self._table_widget.rowCount()):
            citem = self._table_widget.item(r, 0)
            iid = self._table_widget.item(r, 1)
            if (
                citem is not None
                and citem.checkState() == Qt.CheckState.Checked
                and iid is not None
            ):
                selected.append(iid.text())
        return selected

    def _on_header_section_clicked(self, section: int) -> None:
        if section != 0:
            return
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
        if not self._current_trace_type or not self._canvas:
            return

        series_dict = self._feature_series.get(self._current_trace_type, {})
        display_name = self._current_trace_type.replace("_", " ").title()

        if not selected_ids or self._frames.size == 0:
            self._canvas.clear()
            return

        lines_data = []
        styles_data = []
        for trace_id in selected_ids:
            series = series_dict.get(trace_id)
            if series is None:
                continue
            is_active = self._active_trace_id == trace_id
            lines_data.append((self._frames, series))
            styles_data.append(
                {
                    "plot_style": "line",
                    "color": "red" if is_active else "gray",
                    "linewidth": 2.0 if is_active else 1.0,
                    "alpha": 1.0 if is_active else 0.6,
                }
            )

        self._canvas.plot_lines(
            lines_data,
            styles_data,
            title="Traces",
            x_label="Frame",
            y_label=display_name,
        )

    def _on_feature_changed(self, text: str) -> None:
        if not text:
            return

        index = self._feature_dropdown.currentIndex()
        if index >= 0:
            self._current_trace_type = self._feature_dropdown.itemData(index)
            self._plot_selected_traces(self.get_selected_ids())

    def _on_save_clicked(self) -> None:
        if self._traces_csv_path is None:
            QMessageBox.warning(
                self, "Save Good Labels", "No source CSV available to save."
            )
            return
        try:
            selected_ids: set[str] = set()
            for row in range(self._table_widget.rowCount()):
                check_item = self._table_widget.item(row, 0)
                id_item = self._table_widget.item(row, 1)
                if (
                    check_item is not None
                    and id_item is not None
                    and check_item.checkState() == Qt.CheckState.Checked
                ):
                    selected_ids.add(id_item.text())

            # Use ProcessingCSVLoader to load and validate the CSV format
            loader = ProcessingCSVLoader()
            df = loader.load_fov_traces(self._traces_csv_path)

            # Update the 'good' column based on selected traces
            df["good"] = df["cell_id"].astype(str).isin(selected_ids)

            original_name = self._traces_csv_path.name
            if original_name.endswith("traces_inspected.csv"):
                output_name = original_name
            elif original_name.endswith("traces.csv"):
                output_name = original_name.replace(
                    "traces.csv", "traces_inspected.csv"
                )
            else:
                output_name = self._traces_csv_path.stem + "_inspected.csv"
            output_path = self._traces_csv_path.with_name(output_name)

            # Save using standard pandas (ProcessingCSVLoader handles loading validation)
            df.to_csv(output_path, index=False)

            QMessageBox.information(self, "Save Good Labels", f"Saved: {output_path}")
        except Exception as e:
            QMessageBox.critical(
                self, "Save Good Labels", f"Failed to save inspected CSV:\n{e}"
            )
