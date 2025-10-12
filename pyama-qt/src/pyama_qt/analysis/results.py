"""Results panel rendering fitting quality and parameter histograms."""

import logging
from pathlib import Path
from typing import Sequence

import pandas as pd
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from pyama_qt.config import DEFAULT_DIR
from ..base import BasePanel
from ..components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


class ResultsPanel(BasePanel):
    """Right-hand panel visualising fitting diagnostics."""

    saveRequested = Signal(Path)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # --- State from FittedResultsModel ---
        self._results_df: pd.DataFrame | None = None

        # --- State from Controller ---
        self._parameter_names: list[str] = []
        self._selected_parameter: str | None = None

    def build(self) -> None:
        layout = QVBoxLayout(self)
        self._results_group = self._build_results_group()
        layout.addWidget(self._results_group)

    def bind(self) -> None:
        self._param_combo.currentTextChanged.connect(self._on_param_changed)
        self._filter_checkbox.stateChanged.connect(lambda: self._update_histogram())
        self._save_button.clicked.connect(self._on_save_clicked)

    # --- Public Slots for connection to other components ---
    def on_fitting_completed(self, results_df: pd.DataFrame):
        self.set_results(results_df)

    def on_load_fitted_results(self, path: Path):
        try:
            df = pd.read_csv(path)
            self.set_results(df)
            logger.info("Loaded existing fitted results from %s", path)
        except Exception as e:
            logger.warning("Failed to load fitted results from %s: %s", path, e)
            self.clear()

    # --- Internal Logic (from Model and Controller) ---
    def set_results(self, df: pd.DataFrame):
        self._results_df = df
        if df is None or df.empty:
            self.clear()
            return

        self._update_quality_plot()
        self._parameter_names = self._discover_numeric_parameters(df)

        current = self._selected_parameter
        if current not in self._parameter_names:
            current = self._parameter_names[0] if self._parameter_names else None
        self._selected_parameter = current

        self._param_combo.blockSignals(True)
        self._param_combo.clear()
        self._param_combo.addItems(self._parameter_names)
        if current:
            self._param_combo.setCurrentText(current)
        self._param_combo.blockSignals(False)

        self._update_histogram()

    def clear(self):
        self._results_df = None
        self._parameter_names = []
        self._selected_parameter = None
        self._quality_canvas.clear()
        self._param_canvas.clear()
        self._param_combo.clear()

    def _update_quality_plot(self):
        if self._results_df is None or "r_squared" not in self._results_df.columns:
            self._quality_canvas.clear()
            return

        r_squared = pd.to_numeric(self._results_df["r_squared"], errors="coerce").dropna()
        if r_squared.empty:
            self._quality_canvas.clear()
            return

        colors = ["green" if r2 > 0.9 else "orange" if r2 > 0.7 else "red" for r2 in r_squared]
        lines = [(list(range(len(r_squared))), r_squared.values)]
        styles = [{"plot_style": "scatter", "color": colors, "alpha": 0.6, "s": 20}]

        good_pct = (r_squared > 0.9).mean() * 100
        fair_pct = ((r_squared > 0.7) & (r_squared <= 0.9)).mean() * 100
        poor_pct = (r_squared <= 0.7).mean() * 100

        legend_text = f"Good (R²>0.9): {good_pct:.1f}%\nFair (0.7<R²≤0.9): {fair_pct:.1f}%\nPoor (R²≤0.7): {poor_pct:.1f}%"

        self._quality_canvas.plot_lines(
            lines, styles, title="Fitting Quality", x_label="Cell Index", y_label="R²"
        )
        ax = self._quality_canvas.axes
        if ax:
            props = dict(boxstyle="round", facecolor="white", alpha=0.8)
            ax.text(0.98, 0.02, legend_text, transform=ax.transAxes, fontsize=9, verticalalignment="bottom", horizontalalignment="right", bbox=props)

    def _update_histogram(self):
        if self._results_df is None or not self._selected_parameter:
            self._param_canvas.clear()
            return

        series = self._get_histogram_series(self._results_df, self._selected_parameter)
        if series is None or series.empty:
            self._param_canvas.clear()
            return

        self._param_canvas.plot_histogram(
            series.tolist(),
            bins=30,
            title=f"Distribution of {self._selected_parameter}",
            x_label=self._selected_parameter,
            y_label="Frequency",
        )

    def _get_histogram_series(self, df: pd.DataFrame, param_name: str) -> pd.Series | None:
        data = pd.to_numeric(df.get(param_name), errors="coerce").dropna()
        if data.empty:
            return None

        if self._filter_checkbox.isChecked() and "r_squared" in df.columns:
            mask = pd.to_numeric(df["r_squared"], errors="coerce") > 0.9
            data = pd.to_numeric(df.loc[mask, param_name], errors="coerce").dropna()

        return data if not data.empty else None

    def _discover_numeric_parameters(self, df: pd.DataFrame) -> list[str]:
        metadata_cols = {"fov", "file", "cell_id", "model_type", "success", "residual_sum_squares", "message", "n_function_calls", "chisq", "std", "r_squared"}
        return [col for col in df.columns if col not in metadata_cols and pd.to_numeric(df[col], errors='coerce').notna().any()]

    # --- UI Event Handlers ---
    def _on_param_changed(self, name: str):
        if name and name != self._selected_parameter:
            self._selected_parameter = name
            self._update_histogram()

    def _on_save_clicked(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select folder to save histograms", str(DEFAULT_DIR))
        if folder_path:
            self._save_all_histograms(Path(folder_path))

    def _save_all_histograms(self, folder: Path):
        if self._results_df is None or self._results_df.empty:
            return

        current_param = self._selected_parameter
        for param_name in self._parameter_names:
            series = self._get_histogram_series(self._results_df, param_name)
            if series is None or series.empty:
                continue
            # Temporarily render histogram to save it
            self._param_canvas.plot_histogram(series.tolist(), title=f"Distribution of {param_name}", x_label=param_name)
            output_path = folder / f"{param_name}.png"
            self._param_canvas.figure.savefig(output_path, dpi=300, bbox_inches="tight")
            logger.info("Saved histogram to %s", output_path)

        # Restore the originally selected histogram
        if current_param:
            self._selected_parameter = current_param
            self._update_histogram()

    # --- UI builders ---
    def _build_results_group(self) -> QGroupBox:
        group = QGroupBox("Results")
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel("Fitting Quality"))
        self._quality_canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self._quality_canvas)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Parameter:"))
        self._param_combo = QComboBox()
        controls.addWidget(self._param_combo)
        controls.addStretch()
        self._filter_checkbox = QCheckBox("Good Fits Only (R² > 0.9)")
        controls.addWidget(self._filter_checkbox)
        self._save_button = QPushButton("Save All Plots")
        controls.addWidget(self._save_button)
        layout.addLayout(controls)
        self._param_canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self._param_canvas)
        return group