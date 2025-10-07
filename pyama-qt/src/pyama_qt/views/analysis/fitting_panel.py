"""Fitting controls and quality inspection panel."""

from collections.abc import Iterable, Sequence
from typing import Tuple

import pandas as pd
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..base import BasePanel
from ..components.mpl_canvas import MplCanvas
from ..components.parameter_panel import ParameterPanel


class AnalysisFittingPanel(BasePanel):
    """Middle panel offering model selection, fitting, and QC plots."""

    fit_requested = Signal(str, dict, dict, bool)
    visualize_requested = Signal(str)
    shuffle_requested = Signal()
    cell_visualized = Signal(str)
    model_changed = Signal(str)

    def build(self) -> None:
        layout = QVBoxLayout(self)

        self._fitting_group = self._build_fitting_group()
        self._qc_group = self._build_qc_group()

        layout.addWidget(self._fitting_group, 1)
        layout.addWidget(self._qc_group, 1)

        self._current_cell: str | None = None

    def bind(self) -> None:
        self._start_button.clicked.connect(self._on_start_clicked)
        self._visualize_button.clicked.connect(self._on_visualize_clicked)
        self._shuffle_button.clicked.connect(self.shuffle_requested.emit)
        self._model_combo.currentTextChanged.connect(self._on_model_changed)

    # ------------------------------------------------------------------
    # Public API for controllers
    # ------------------------------------------------------------------
    def set_available_models(self, model_names: Sequence[str]) -> None:
        """Populate the model chooser with provided names."""
        current = self._model_combo.currentText()
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItems(model_names)
        if current in model_names:
            self._model_combo.setCurrentText(current)
        self._model_combo.blockSignals(False)

    def set_parameter_defaults(self, parameters: pd.DataFrame) -> None:
        """Replace the parameter table with defaults supplied by controller."""
        self._param_panel.set_parameters_df(parameters)

    def set_fitting_active(self, is_active: bool) -> None:
        """Toggle progress feedback while fitting is running."""
        if is_active:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.show()
        else:
            self._progress_bar.hide()

    def clear_qc_view(self) -> None:
        """Reset the quality-control plot."""
        self._qc_canvas.clear()
        self._current_cell = None

    def show_cell_visualization(
        self,
        *,
        cell_name: str,
        lines: Iterable[tuple[Sequence[float], Sequence[float]]],
        styles: Iterable[dict],
        title: str,
        x_label: str,
        y_label: str,
    ) -> None:
        """Render QC plot for a specific cell."""
        line_payload = tuple(lines)
        style_payload = tuple(styles)
        if not line_payload:
            self.clear_qc_view()
            return

        self._qc_canvas.plot_lines(
            line_payload,
            style_payload,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
        self._current_cell = cell_name
        self._cell_input.setText(cell_name)
        self.cell_visualized.emit(cell_name)

    def set_cell_candidate(self, cell_name: str) -> None:
        """Update the cell input field without triggering visualization."""
        self._cell_input.setText(cell_name)

    # ------------------------------------------------------------------
    # Internal event handlers
    # ------------------------------------------------------------------
    def _on_start_clicked(self) -> None:
        model_type = self._model_combo.currentText().strip().lower()
        params = self._collect_model_params()
        bounds = self._collect_model_bounds()
        manual = self._param_panel.use_manual_params.isChecked()
        self.fit_requested.emit(model_type, params, bounds, manual)

    def _on_visualize_clicked(self) -> None:
        cell_name = self._cell_input.text().strip()
        if cell_name:
            self.visualize_requested.emit(cell_name)

    def _on_model_changed(self) -> None:
        model_type = self._model_combo.currentText().strip().lower()
        self.model_changed.emit(model_type)

    # ------------------------------------------------------------------
    # Helpers for packaging parameter data
    # ------------------------------------------------------------------
    def _collect_model_params(self) -> dict:
        df = self._param_panel.get_values_df()
        if df is None or df.empty:
            return {}
        if "value" in df.columns:
            return df["value"].to_dict()
        first_col = df.columns[0]
        return df[first_col].to_dict()

    def _collect_model_bounds(self) -> dict:
        df = self._param_panel.get_values_df()
        if df is None or df.empty or "min" not in df.columns or "max" not in df.columns:
            return {}
        bounds: dict[str, Tuple[float, float]] = {}
        for name, row in df.iterrows():
            min_v = row.get("min")
            max_v = row.get("max")
            if pd.notna(min_v) and pd.notna(max_v):
                try:
                    bounds[name] = (float(min_v), float(max_v))
                except Exception:
                    continue
        return bounds

    # ------------------------------------------------------------------
    # UI building helpers
    # ------------------------------------------------------------------
    def _build_fitting_group(self) -> QGroupBox:
        group = QGroupBox("Fitting")
        group_layout = QVBoxLayout(group)

        form = QFormLayout()
        self._model_combo = QComboBox()
        form.addRow("Model:", self._model_combo)
        group_layout.addLayout(form)

        self._param_panel = ParameterPanel()
        group_layout.addWidget(self._param_panel)

        self._start_button = QPushButton("Start Fitting")
        group_layout.addWidget(self._start_button)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        group_layout.addWidget(self._progress_bar)

        return group

    def _build_qc_group(self) -> QGroupBox:
        group = QGroupBox("Quality Check")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        self._cell_input = QLineEdit()
        self._cell_input.setPlaceholderText("Enter cell ID (column name)")
        row.addWidget(self._cell_input)

        self._visualize_button = QPushButton("Visualize")
        row.addWidget(self._visualize_button)

        self._shuffle_button = QPushButton("Shuffle")
        row.addWidget(self._shuffle_button)
        layout.addLayout(row)

        self._qc_canvas = MplCanvas(self, width=5, height=3)
        layout.addWidget(self._qc_canvas)

        return group
