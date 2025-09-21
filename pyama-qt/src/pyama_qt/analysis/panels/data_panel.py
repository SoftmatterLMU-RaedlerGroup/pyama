"""Data panel for loading CSV files and plotting traces."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_qt.analysis.state import AnalysisState
from pyama_qt.components import MplCanvas
from pyama_qt.ui import BasePanel


class AnalysisDataPanel(BasePanel[AnalysisState]):
    """Left-side panel responsible for loading CSV data and visualisation."""

    csv_selected = Signal(Path)

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
        if state is None or state.raw_data is None:
            self._canvas.clear()
            return

        self._plot_all_sequences(state)

    # ------------------------------------------------------------------
    # Public helpers used by the page
    # ------------------------------------------------------------------
    def highlight_cell(self, cell_id: str) -> bool:
        state = self.get_state()
        if state is None or state.raw_data is None:
            return False

        if cell_id not in state.raw_data.columns:
            return False

        data = state.raw_data
        time_values = data.index.values

        lines = []
        styles = []
        for other_id in data.columns[:50]:
            if other_id != cell_id:
                lines.append((time_values, data[other_id].values))
                styles.append(
                    {
                        "plot_style": "line",
                        "color": "gray",
                        "alpha": 0.1,
                        "linewidth": 0.5,
                    }
                )

        lines.append((time_values, data[cell_id].values))
        styles.append(
            {
                "plot_style": "line",
                "color": "blue",
                "linewidth": 2,
                "label": f"Cell {cell_id}",
            }
        )

        self._canvas.plot_lines(
            lines,
            styles,
            title=f"Cell {cell_id} Highlighted",
            x_label="Time",
            y_label="Intensity",
        )
        return True

    def random_cell_id(self) -> Optional[str]:
        state = self.get_state()
        if state is None or state.raw_data is None:
            return None
        columns = state.raw_data.columns
        if len(columns) == 0:
            return None
        return str(np.random.choice(columns))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _on_load_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            "",
            "CSV Files (*.csv)",
            options=QFileDialog.DontUseNativeDialog,
        )
        if file_path:
            self.csv_selected.emit(Path(file_path))

    def _plot_all_sequences(self, state: AnalysisState) -> None:
        data = state.raw_data
        if data is None:
            self._canvas.clear()
            return

        time_values = data.index.values
        lines = []
        styles = []

        for col in data.columns:
            lines.append((time_values, data[col].values))
            styles.append(
                {
                    "plot_style": "line",
                    "color": "gray",
                    "alpha": 0.2,
                    "linewidth": 0.5,
                }
            )

        if not data.empty:
            lines.append((time_values, data.mean(axis=1).values))
            styles.append(
                {
                    "plot_style": "line",
                    "color": "red",
                    "linewidth": 2,
                    "label": "Mean",
                }
            )

        self._canvas.plot_lines(
            lines,
            styles,
            title=f"All Sequences ({len(data.columns)} cells)",
            x_label="Time",
            y_label="Intensity",
        )
