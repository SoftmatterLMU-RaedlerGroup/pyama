"""Results panel rendering fitting quality and parameter histograms."""

from __future__ import annotations

import pandas as pd
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

from pyama_qt.analysis.state import AnalysisState
from pyama_qt.components import MplCanvas
from pyama_qt.config import DEFAULT_DIR
from pyama_qt.ui import BasePanel


class AnalysisResultsPanel(BasePanel[AnalysisState]):
    """Right-hand panel visualising fitting diagnostics."""

    def build(self) -> None:
        layout = QVBoxLayout(self)
        self._results_group = self._build_results_group()
        layout.addWidget(self._results_group)

    def bind(self) -> None:
        self._param_combo.currentTextChanged.connect(self._update_param_histogram)
        self._filter_checkbox.stateChanged.connect(self._update_param_histogram)
        self._save_button.clicked.connect(self._save_histogram)

    def update_view(self) -> None:
        state = self.get_state()
        if state is None or state.fitted_results is None or state.fitted_results.empty:
            self._quality_canvas.clear()
            self._param_canvas.clear()
            return

        self._draw_quality_chart(state.fitted_results)
        self._populate_parameter_choices(state.fitted_results)
        self._update_param_histogram()

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------
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
        self._filter_checkbox = QCheckBox("Good Fits Only")
        controls.addWidget(self._filter_checkbox)

        self._save_button = QPushButton("Save Plot")
        controls.addWidget(self._save_button)

        layout.addLayout(controls)

        self._param_canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self._param_canvas)

        return group

    # ------------------------------------------------------------------
    # Plot helpers
    # ------------------------------------------------------------------
    def _draw_quality_chart(self, results: pd.DataFrame) -> None:
        r_squared_series = pd.to_numeric(
            results.get("r_squared"), errors="coerce"
        ).dropna()
        if r_squared_series.empty:
            self._quality_canvas.clear()
            return

        colors = [
            "green" if r2 > 0.9 else "orange" if r2 > 0.7 else "red"
            for r2 in r_squared_series
        ]
        lines = [(range(len(r_squared_series)), r_squared_series.values)]
        styles = [
            {
                "plot_style": "scatter",
                "color": colors,
                "alpha": 0.6,
                "s": 20,
            }
        ]

        good_pct = (r_squared_series > 0.9).mean() * 100
        fair_pct = ((r_squared_series > 0.7) & (r_squared_series <= 0.9)).mean() * 100
        poor_pct = (r_squared_series <= 0.7).mean() * 100

        self._quality_canvas.plot_lines(
            lines,
            styles,
            title="Fitting Quality",
            x_label="Cell Index",
            y_label="R²",
        )

        ax = self._quality_canvas.axes
        if ax:
            props = dict(boxstyle="round", facecolor="white", alpha=0.8)
            legend_text = (
                f"Good (R²>0.9): {good_pct:.1f}%\n"
                f"Fair (0.7<R²≤0.9): {fair_pct:.1f}%\n"
                f"Poor (R²≤0.7): {poor_pct:.1f}%"
            )
            ax.text(
                0.98,
                0.02,
                legend_text,
                transform=ax.transAxes,
                fontsize=9,
                verticalalignment="bottom",
                horizontalalignment="right",
                bbox=props,
            )

    def _populate_parameter_choices(self, results: pd.DataFrame) -> None:
        metadata_cols = {
            "fov",
            "file",
            "cell_id",
            "model_type",
            "success",
            "residual_sum_squares",
            "message",
            "n_function_calls",
            "chisq",
            "std",
            "r_squared",
        }

        numeric_cols = []
        for col in results.columns:
            if col in metadata_cols:
                continue
            numeric = pd.to_numeric(results[col], errors="coerce")
            if numeric.notna().any():
                numeric_cols.append(col)

        current = self._param_combo.currentText()
        self._param_combo.blockSignals(True)
        self._param_combo.clear()
        if numeric_cols:
            self._param_combo.addItems(numeric_cols)
            if current in numeric_cols:
                self._param_combo.setCurrentText(current)
        self._param_combo.blockSignals(False)

    def _update_param_histogram(self) -> None:
        state = self.get_state()
        if state is None or state.fitted_results is None:
            self._param_canvas.clear()
            return

        param_name = self._param_combo.currentText()
        if not param_name or param_name not in state.fitted_results.columns:
            self._param_canvas.clear()
            return

        data = self._get_histogram_data(state.fitted_results, param_name)
        if data is None:
            self._param_canvas.clear()
            return

        self._plot_histogram(param_name, data)

    def _get_histogram_data(
        self, results: pd.DataFrame, param_name: str
    ) -> pd.Series | None:
        """Get histogram data for a parameter, applying filters if needed."""
        data = pd.to_numeric(results[param_name], errors="coerce").dropna()
        if data.empty:
            return None

        if self._filter_checkbox.isChecked() and "r_squared" in results.columns:
            mask = pd.to_numeric(results["r_squared"], errors="coerce") > 0.9
            data = pd.to_numeric(
                results.loc[mask, param_name], errors="coerce"
            ).dropna()
            if data.empty:
                return None

        return data

    def _plot_histogram(self, param_name: str, data: pd.Series) -> None:
        """Plot histogram for given parameter data."""
        self._param_canvas.plot_histogram(
            data.values,
            bins=30,
            title=f"Distribution of {param_name}",
            x_label=param_name,
            y_label="Frequency",
        )

    def _save_histogram(self) -> None:
        """Save histogram plots for all parameters to PNG files."""
        state = self.get_state()
        if state is None or state.fitted_results is None:
            return

        # Get all available parameter names
        param_names = [
            self._param_combo.itemText(i) for i in range(self._param_combo.count())
        ]
        if not param_names:
            return

        # Open folder dialog to choose save location
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select folder to save histograms",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )

        if folder_path:
            # Save current selection to restore later
            current_param = self._param_combo.currentText()

            for param_name in param_names:
                try:
                    # Generate histogram data for this parameter
                    data = self._get_histogram_data(state.fitted_results, param_name)
                    if data is None:
                        continue

                    # Create and save the plot
                    self._plot_histogram(param_name, data)

                    file_path = f"{folder_path}/{param_name}.png"
                    self._param_canvas.figure.savefig(
                        file_path, dpi=300, bbox_inches="tight"
                    )
                except Exception as e:
                    print(f"Error saving plot for {param_name}: {e}")

            # Restore the original selection and update display
            if current_param:
                self._param_combo.setCurrentText(current_param)
                self._update_param_histogram()
