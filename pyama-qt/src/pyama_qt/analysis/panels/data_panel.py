"""Data panel for loading CSV files and plotting traces."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
)

from pyama_qt.analysis.models import AnalysisDataModel
from pyama_qt.components import MplCanvas
from pyama_qt.config import DEFAULT_DIR
from pyama_qt.ui import ModelBoundPanel


import hashlib  # For hash


class AnalysisDataPanel(ModelBoundPanel):
    """Left-side panel responsible for loading CSV data and visualisation."""

    csv_selected = Signal(Path)
    highlight_requested = Signal(str)
    random_cell_requested = Signal()

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
        data_model.plotDataChanged.connect(self._on_plot_data_changed)
        data_model.plotTitleChanged.connect(self._on_plot_title_changed)

    # ------------------------------------------------------------------
    # Public helpers used by the page
    # ------------------------------------------------------------------
    def _on_highlight_requested(self, cell_id: str) -> None:
        self.highlight_requested.emit(cell_id)

    def _on_random_cell_requested(self) -> None:
        self.random_cell_requested.emit()

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

    def _on_plot_data_changed(self, plot_data) -> None:
        if plot_data is None:
            self._canvas.clear()
            self._last_plot_hash = None
            return

        new_hash = hashlib.md5(str(plot_data).encode()).hexdigest()
        if new_hash != self._last_plot_hash:
            self._canvas.plot_lines(
                plot_data,
                title=self._current_title,
                x_label="Time",
                y_label="Intensity",
            )
            self._last_plot_hash = new_hash

    def _on_plot_title_changed(self, title: str) -> None:
        self._current_title = title
