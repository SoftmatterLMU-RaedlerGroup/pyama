"""Data panel for loading CSV files and plotting traces."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
)

from pyama_qt.analysis.state import AnalysisState
from pyama_qt.components import MplCanvas
from pyama_qt.config import DEFAULT_DIR
from pyama_qt.ui import BasePanel

from typing import List, Tuple

import hashlib  # For hash

# Change signals:
plot_requested = Signal()
highlight_requested = Signal(str)
random_cell_requested = Signal()


class AnalysisDataPanel(BasePanel[AnalysisState]):
    """Left-side panel responsible for loading CSV data and visualisation."""

    csv_selected = Signal(Path)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_plot_hash: str | None = None  # New

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

    def update_view(self) -> None:
        state = self.get_state()
        if state is None:
            self._last_plot_hash = None
            self._canvas.clear()
            return

        if state.plot_data is None:
            if self._last_plot_hash is not None:
                self._canvas.clear()
                self._last_plot_hash = None
            return

        import hashlib

        new_hash = hashlib.md5(str(state.plot_data).encode()).hexdigest()
        if new_hash != self._last_plot_hash:
            self._canvas.plot_lines(
                state.plot_data,
                title=state.plot_title or "",
                x_label="Time",
                y_label="Intensity",
            )
            self._last_plot_hash = new_hash

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
            self.plot_requested.emit()
