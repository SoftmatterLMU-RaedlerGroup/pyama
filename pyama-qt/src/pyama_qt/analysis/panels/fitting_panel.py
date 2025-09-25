"""Fitting controls and quality inspection panel."""

from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from pyama_core.analysis.fitting import get_trace
from pyama_core.analysis.models import get_model, get_types

from pyama_qt.analysis.state import AnalysisState, FittingRequest
from pyama_qt.components import MplCanvas, ParameterPanel
from pyama_qt.ui import BasePanel


class AnalysisFittingPanel(BasePanel[AnalysisState]):
    """Middle panel offering model selection, fitting, and QC plots."""

    fit_requested = Signal(object)  # FittingRequest
    cell_visualized = Signal(str)

    def build(self) -> None:
        layout = QVBoxLayout(self)

        self._fitting_group = self._build_fitting_group()
        self._qc_group = self._build_qc_group()

        layout.addWidget(self._fitting_group, 1)
        layout.addWidget(self._qc_group, 1)

        self._current_cell: str | None = None

    def bind(self) -> None:
        self._model_combo.currentTextChanged.connect(self._update_model_params)
        self._start_button.clicked.connect(self._on_start_clicked)
        self._visualize_button.clicked.connect(self._on_visualize_clicked)
        self._shuffle_button.clicked.connect(self._on_shuffle_clicked)

    def update_view(self) -> None:
        state = self.get_state()
        if state is None:
            return

        if state.is_fitting:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.show()
        else:
            self._progress_bar.hide()

        if state.fitted_results is not None and self._current_cell:
            self._visualize_cell(self._current_cell)

    # ------------------------------------------------------------------
    # UI building helpers
    # ------------------------------------------------------------------
    def _build_fitting_group(self) -> QGroupBox:
        group = QGroupBox("Fitting")
        group_layout = QVBoxLayout(group)

        form = QFormLayout()
        self._model_combo = QComboBox()
        self._model_combo.addItems(["Trivial", "Maturation"])
        form.addRow("Model:", self._model_combo)
        group_layout.addLayout(form)

        self._param_panel = ParameterPanel()
        group_layout.addWidget(self._param_panel)
        self._update_model_params()

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

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_start_clicked(self) -> None:
        state = self.get_state()
        if state is None or state.raw_csv_path is None:
            QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        request = FittingRequest(
            model_type=self._model_combo.currentText().lower(),
            model_params=self._collect_model_params(),
            model_bounds=self._collect_model_bounds(),
        )
        self.fit_requested.emit(request)

    def _on_visualize_clicked(self) -> None:
        cell_name = self._cell_input.text().strip()
        if not cell_name:
            return
        if not self._visualize_cell(cell_name):
            QMessageBox.warning(
                self, "Cell Not Found", f"Cell '{cell_name}' not found."
            )

    def _on_shuffle_clicked(self) -> None:
        state = self.get_state()
        if state is None or state.raw_data is None or state.raw_data.empty:
            return
        cell_name = str(np.random.choice(state.raw_data.columns))
        self._cell_input.setText(cell_name)
        self._visualize_cell(cell_name)

    # ------------------------------------------------------------------
    # Internal logic
    # ------------------------------------------------------------------

    def _update_model_params(self) -> None:
        model_type = self._model_combo.currentText().lower()
        try:
            model = get_model(model_type)
            types = get_types(model_type)
            UserParams = types["UserParams"]
            user_param_names = list(UserParams.__annotations__.keys())
            rows = []
            for param_name in user_param_names:
                default_val = model.DEFAULTS[param_name]
                min_val, max_val = model.BOUNDS[param_name]
                rows.append(
                    {
                        "name": param_name,
                        "value": default_val,
                        "min": min_val,
                        "max": max_val,
                    }
                )
            df = pd.DataFrame(rows).set_index("name") if rows else pd.DataFrame()
        except Exception:
            df = pd.DataFrame()
        self._param_panel.set_parameters_df(df)

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
        if df is None or df.empty:
            return {}
        if "min" not in df.columns or "max" not in df.columns:
            return {}
        bounds: dict[str, tuple[float, float]] = {}
        for name, row in df.iterrows():
            min_v = row.get("min")
            max_v = row.get("max")
            if pd.notna(min_v) and pd.notna(max_v):
                try:
                    bounds[name] = (float(min_v), float(max_v))
                except Exception:
                    continue
        return bounds

    def _visualize_cell(self, cell_name: str) -> bool:
        state = self.get_state()
        if state is None or state.raw_data is None:
            return False
        if cell_name not in state.raw_data.columns:
            return False

        cell_index = list(state.raw_data.columns).index(cell_name)
        time_data, intensity_data = get_trace(state.raw_data, cell_index)

        lines = [(time_data, intensity_data)]
        styles = [
            {
                "plot_style": "scatter",
                "color": "blue",
                "alpha": 0.6,
                "s": 20,
                "label": f"{cell_name} (data)",
            }
        ]

        self._add_fitted_curve(cell_index, time_data, lines, styles)

        self._qc_canvas.plot_lines(
            lines,
            styles,
            title=f"Quality Control - {cell_name}",
            x_label="Time",
            y_label="Intensity",
        )
        self._current_cell = cell_name
        self.cell_visualized.emit(cell_name)
        return True

    def _add_fitted_curve(self, cell_index: int, time_data, lines, styles) -> None:
        state = self.get_state()
        if state is None or state.fitted_results is None or state.fitted_results.empty:
            return

        cell_fit = state.fitted_results[state.fitted_results["cell_id"] == cell_index]
        if cell_fit.empty:
            return

        first_fit = cell_fit.iloc[0]
        success_val = first_fit.get("success")
        if not (
            success_val in [True, "True", "true", 1, "1"]
            or (isinstance(success_val, str) and success_val.lower() == "true")
        ):
            return

        model_type = first_fit.get("model_type", "").lower()
        try:
            model = get_model(model_type)
            param_names = list(model.DEFAULTS.keys())
            params_dict = {}
            for p in param_names:
                if p in cell_fit.columns and pd.notna(first_fit[p]):
                    params_dict[p] = float(first_fit[p])
            if len(params_dict) == len(param_names):
                t_smooth = np.linspace(time_data.min(), time_data.max(), 200)
                y_fit = model.eval(t_smooth, params_dict)
                r_squared = float(first_fit.get("r_squared", 0))
                lines.append((t_smooth, y_fit))
                styles.append(
                    {
                        "plot_style": "line",
                        "color": "red",
                        "linewidth": 2,
                        "label": f"Fit (R²={r_squared:.3f})",
                    }
                )
        except Exception:
            pass
