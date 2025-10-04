"""Data panel for loading CSV files and plotting traces."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
)

from pyama_qt.models.analysis import AnalysisDataModel
from ..components.mpl_canvas import MplCanvas
from pyama_qt.config import DEFAULT_DIR
from ..base import ModelBoundPanel


import hashlib  # For hash


class AnalysisDataPanel(ModelBoundPanel):
    """Left-side panel responsible for loading CSV data and visualisation."""

    csv_selected = Signal(Path)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_plot_hash: str | None = None  # New
        self._current_title = ""

    def build(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Data")
        group_layout = QVBoxLayout(group)

        self._load_button = QPushButton("Load CSV")
        group_layout.addWidget(self._load_button)

        self._canvas = MplCanvas(self, width=5, height=8)
        group_layout.addWidget(self._canvas)
        self._canvas.clear()

        layout.addWidget(group)

    def bind(self) -> None:
        self._load_button.clicked.connect(self._on_load_clicked)

    def set_models(self, data_model: AnalysisDataModel) -> None:
        self._data_model = data_model
        data_model.rawDataChanged.connect(self._on_raw_data_changed)
        data_model.plotTitleChanged.connect(self._on_plot_title_changed)


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _on_load_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            DEFAULT_DIR,
            "CSV Files (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self.csv_selected.emit(Path(file_path))

    def _on_raw_data_changed(self, raw_data) -> None:
        if raw_data is None:
            self._canvas.clear()
            self._last_plot_hash = None
            return

        # Always show the "all lines + mean" view regardless of any highlighting elsewhere
        self._data_model.prepare_all_plot()
        plot_data = self._data_model._plot_data

        if plot_data is None:
            self._canvas.clear()
            return

        new_hash = hashlib.md5(str(plot_data).encode()).hexdigest()
        if new_hash != self._last_plot_hash:
            # Extract lines_data and styles_data from plot_data
            # plot_data is a list of (x_data, y_data, style_dict) tuples
            lines_data = [(x_data, y_data) for x_data, y_data, _ in plot_data]
            styles_data = [style_dict for _, _, style_dict in plot_data]

            self._canvas.plot_lines(
                lines_data,
                styles_data,
                title=self._current_title,
                x_label="Time (hours)",
                y_label="Intensity",
            )
            self._last_plot_hash = new_hash

    def _on_plot_title_changed(self, title: str) -> None:
        self._current_title = title
