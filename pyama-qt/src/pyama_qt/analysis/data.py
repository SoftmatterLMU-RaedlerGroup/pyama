"""Data panel for loading CSV files and plotting traces."""

import hashlib
import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
)

from pyama_core.io.analysis_csv import load_analysis_csv
from pyama_qt.config import DEFAULT_DIR
from ..base import BasePanel
from ..components.mpl_canvas import MplCanvas


PlotLine = tuple[Sequence[float], Sequence[float], dict]

logger = logging.getLogger(__name__)


class DataPanel(BasePanel):
    """Left-side panel responsible for loading CSV data and visualisation."""

    # Signals for other components to connect to
    rawDataChanged = Signal(object)  # pd.DataFrame
    rawCsvPathChanged = Signal(object)  # Path
    # This signal will be used by the fitting panel to get a random cell
    cellHighlighted = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_plot_hash: str | None = None
        self._current_title = ""

        # --- State from AnalysisDataModel ---
        self._raw_data: pd.DataFrame | None = None
        self._raw_csv_path: Path | None = None
        self._selected_cell: str | None = None

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

    # --- Public API for other components ---
    def raw_data(self) -> pd.DataFrame | None:
        return self._raw_data

    def raw_csv_path(self) -> Path | None:
        return self._raw_csv_path

    def get_random_cell(self) -> str | None:
        """Get a random cell ID."""
        if self._raw_data is None or self._raw_data.empty:
            return None
        return str(np.random.choice(self._raw_data.columns))

    def highlight_cell(self, cell_id: str) -> None:
        """Highlight a specific cell in the plot."""
        if self._raw_data is None or cell_id not in self._raw_data.columns:
            return
        self._selected_cell = cell_id

        data = self._raw_data
        time_values = data.index.values

        lines_data = []
        styles_data = []

        for other_id in data.columns:
            if other_id != cell_id:
                lines_data.append((time_values, data[other_id].values))
                styles_data.append({"color": "gray", "alpha": 0.1, "linewidth": 0.5})

        lines_data.append((time_values, data[cell_id].values))
        styles_data.append({"color": "blue", "linewidth": 2, "label": f"Cell {cell_id}"})

        self._render_plot_internal(
            lines_data,
            styles_data,
            title=f"Cell {cell_id} Highlighted",
        )
        # Emit signal so other components (like fitting panel) know which cell is visualized.
        self.cellHighlighted.emit(cell_id)

    def clear_all(self):
        """Clear data, plot, and state."""
        self._raw_data = None
        self._raw_csv_path = None
        self._selected_cell = None
        self.clear_plot()
        self.rawDataChanged.emit(pd.DataFrame())
        self.rawCsvPathChanged.emit(Path())

    # --- Internal Logic (previously in Model/Controller) ---
    def _load_csv(self, path: Path) -> None:
        """Load CSV data and prepare initial plot."""
        logger.info("Loading analysis CSV from %s", path)
        try:
            df = load_analysis_csv(path)
            self._raw_data = df
            self._raw_csv_path = path

            self._prepare_all_plot()

            # Emit signals after data is loaded and plot is prepared
            self.rawDataChanged.emit(df)
            self.rawCsvPathChanged.emit(path)

        except Exception:
            logger.exception("Failed to load analysis CSV")
            # Maybe show an error message to the user? For now, just log.
            self.clear_all()

    def _prepare_all_plot(self) -> None:
        """Prepare plot data for all traces."""
        if self._raw_data is None:
            self.clear_plot()
            return

        data = self._raw_data
        time_values = data.index.values
        lines_data = []
        styles_data = []

        for col in data.columns:
            lines_data.append((time_values, data[col].values))
            styles_data.append({"color": "gray", "alpha": 0.2, "linewidth": 0.5})

        # Mean line
        if not data.empty:
            mean = data.mean(axis=1).values
            lines_data.append((time_values, mean))
            styles_data.append({"color": "red", "linewidth": 2, "label": "Mean"})

        self._render_plot_internal(
            lines_data,
            styles_data,
            title=f"All Sequences ({len(data.columns)} cells)",
        )

    # --- Plotting Methods (from original Panel) ---
    def clear_plot(self) -> None:
        """Reset the canvas to an empty state."""
        self._canvas.clear()
        self._last_plot_hash = None

    def _render_plot_internal(
        self,
        lines_data: list,
        styles_data: list,
        *,
        title: str = "",
        x_label: str = "Time (hours)",
        y_label: str = "Intensity",
    ) -> None:
        """Internal method to render the plot."""
        cached_payload = (tuple(map(repr, lines_data)), tuple(map(repr, styles_data)))
        new_hash = hashlib.md5(repr(cached_payload).encode()).hexdigest()

        if new_hash == self._last_plot_hash and title == self._current_title:
            return

        self._canvas.plot_lines(
            lines_data,
            styles_data,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
        self._last_plot_hash = new_hash
        self._current_title = title

    # --- UI Event Handlers (from original Panel) ---
    def _on_load_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            str(DEFAULT_DIR),  # QFileDialog needs a string path
            "CSV Files (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._load_csv(Path(file_path))