"""Data panel for loading CSV files and plotting traces."""

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
)

from pyama_qt.config import DEFAULT_DIR
from ..base import BasePanel
from ..components.mpl_canvas import MplCanvas


PlotLine = tuple[Sequence[float], Sequence[float], dict]


class AnalysisDataPanel(BasePanel):
    """Left-side panel responsible for loading CSV data and visualisation."""

    csv_selected = Signal(Path)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_plot_hash: str | None = None
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

    # ------------------------------------------------------------------
    # Public API for controllers
    # ------------------------------------------------------------------
    def clear_plot(self) -> None:
        """Reset the canvas to an empty state."""
        self._canvas.clear()
        self._last_plot_hash = None

    def render_plot(
        self,
        plot_data: Iterable[PlotLine] | None,
        *,
        title: str = "",
        x_label: str = "Time (hours)",
        y_label: str = "Intensity",
    ) -> None:
        """Render the provided plot payload if it changed."""
        if not plot_data:
            self.clear_plot()
            self._current_title = title
            return

        cached_payload = tuple(plot_data)
        new_hash = hashlib.md5(repr(cached_payload).encode()).hexdigest()
        if new_hash == self._last_plot_hash and title == self._current_title:
            return

        lines_data = [(x_data, y_data) for x_data, y_data, _ in cached_payload]
        styles_data = [style_dict for _, _, style_dict in cached_payload]

        self._canvas.plot_lines(
            lines_data,
            styles_data,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
        self._last_plot_hash = new_hash
        self._current_title = title

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
