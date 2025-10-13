"""Fitting quality inspection panel."""

import hashlib
import logging
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_core.analysis.fitting import (
    get_trace,
    analyze_fitting_quality,
)
from pyama_core.analysis.models import get_model

from ..components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


class FittingPanel(QWidget):
    """Middle panel visualising fitting diagnostics and individual fits."""

    # Signals for other components to connect to
    cell_visualized = Signal(str)  # Used to highlight cell in data panel
    shuffle_requested = Signal()  # Request a random cell from data panel
    fittingCompleted = Signal(object)  # pd.DataFrame
    statusMessage = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_plot_hash: str | None = None
        self._current_title = ""
        self.build()
        self.bind()
        # --- State ---
        self._results_df: pd.DataFrame | None = None
        self._raw_data: pd.DataFrame | None = None
        self._selected_cell: str | None = None

        # --- UI Components ---
        self._qc_group: QGroupBox | None = None
        self._trace_group: QGroupBox | None = None

    def build(self) -> None:
        layout = QVBoxLayout(self)

        # Add quality plot group
        self._qc_group = self._build_qc_group()
        layout.addWidget(self._qc_group)

        # Add trace visualization group
        self._trace_group = self._build_trace_group()
        layout.addWidget(self._trace_group)

    def _build_qc_group(self) -> QGroupBox:
        group = QGroupBox("Fitting Quality")
        layout = QVBoxLayout(group)

        # Quality plot on top
        self._qc_canvas = MplCanvas(self)  # Reduced height
        layout.addWidget(self._qc_canvas)

        return group

    def _build_trace_group(self) -> QGroupBox:
        group = QGroupBox("Fitted Traces")
        layout = QVBoxLayout(group)

        # Add shuffle button for trace visualization
        controls_layout = QHBoxLayout()
        self._shuffle_button = QPushButton("Show Random Trace")
        controls_layout.addWidget(self._shuffle_button)
        controls_layout.addStretch()  # Push button to the left
        layout.addLayout(controls_layout)

        self._trace_canvas = MplCanvas(self)  # Lower half height
        layout.addWidget(self._trace_canvas)

        return group

    def bind(self) -> None:
        # Add shuffle button functionality
        self._shuffle_button.clicked.connect(self._on_shuffle_clicked)

    # --- Public Slots for connection to other components ---
    def on_fitting_completed(self, results_df: pd.DataFrame):
        self.set_results(results_df)

    def on_raw_data_changed(self, df: pd.DataFrame):
        self._raw_data = df
        # Update the trace plot with the currently selected cell
        if self._selected_cell:
            self._update_trace_plot(self._selected_cell)

    def on_raw_csv_path_changed(self, path: Path):
        # For now, just accept the signal, we don't need to do anything specific here
        pass

    def on_shuffle_requested(self, get_random_cell_func):
        """Shuffle visualization to a random cell."""
        logger.debug("UI Event: Shuffle requested")
        cell_id = get_random_cell_func()
        if cell_id:
            logger.debug("UI Action: Selected random cell - %s", cell_id)
            self._selected_cell = cell_id
            self._update_trace_plot(cell_id)
            self.cell_visualized.emit(cell_id)
        else:
            logger.debug("UI Action: No cells available for shuffle")

    def _on_shuffle_clicked(self):
        """Handle shuffle button click."""
        logger.debug("UI Click: Shuffle button")
        self.shuffle_requested.emit()

    def on_fitted_results_changed(self, results_df: pd.DataFrame):
        self.set_results(results_df)

    # --- Internal Logic ---
    def set_results(self, df: pd.DataFrame):
        self._results_df = df
        if df is None or df.empty:
            self.clear()
            return

        self._update_quality_plot()

    def clear(self):
        self._results_df = None
        self._raw_data = None
        self._qc_canvas.clear()
        self._trace_canvas.clear()
        self._selected_cell = None

    def _update_quality_plot(self):
        if self._results_df is None or "r_squared" not in self._results_df.columns:
            self._qc_canvas.clear()
            return

        quality_metrics = analyze_fitting_quality(self._results_df)
        if not quality_metrics:
            self._qc_canvas.clear()
            return

        r_squared_values = quality_metrics["r_squared_values"]
        cell_indices = quality_metrics["cell_indices"]
        colors = quality_metrics["colors"]

        lines = [(cell_indices, r_squared_values)]
        styles = [{"plot_style": "scatter", "color": colors, "alpha": 0.6, "s": 20}]

        good_pct = quality_metrics["good_percentage"]
        fair_pct = quality_metrics["fair_percentage"]
        poor_pct = quality_metrics["poor_percentage"]

        legend_text = f"Good (R²>0.9): {good_pct:.1f}%\nFair (0.7<R²≤0.9): {fair_pct:.1f}%\nPoor (R²≤0.7): {poor_pct:.1f}%"

        self._qc_canvas.plot_lines(
            lines, styles, title="Fitting Quality", x_label="Cell Index", y_label="R²"
        )
        ax = self._qc_canvas.axes
        if ax:
            props = dict(boxstyle="round", facecolor="white", alpha=0.8)
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

    def _update_trace_plot(self, cell_id: str):
        """Update the trace plot with raw data and fitted curve."""
        if self._raw_data is None or cell_id not in self._raw_data.columns:
            self._trace_canvas.clear()
            return

        # Get the raw trace data
        time_data, trace_data = get_trace(self._raw_data, cell_id)

        # Prepare to get fitted parameters if available
        fitted_params = None
        model_type = None
        r_squared = None

        if self._results_df is not None:
            # Find the corresponding row in results for this cell_id
            result_row = self._results_df[self._results_df["cell_id"] == cell_id]
            if not result_row.empty:
                result_row = result_row.iloc[0]
                if "model_type" in result_row:
                    model_type = result_row["model_type"]
                if "r_squared" in result_row:
                    r_squared = result_row["r_squared"]

                # Get fitted parameters (excluding special columns)
                special_cols = {"cell_id", "model_type", "success", "r_squared"}
                fitted_params = {
                    col: result_row[col]
                    for col in result_row.index
                    if col not in special_cols and pd.notna(result_row[col])
                }

        # Create the plot
        lines_data = []
        styles_data = []

        # Plot raw data
        lines_data.append((time_data, trace_data))
        styles_data.append(
            {"color": "blue", "alpha": 0.7, "label": f"Raw: {cell_id}", "linewidth": 1}
        )

        # Plot fitted curve if parameters are available
        if fitted_params and model_type:
            try:
                model = get_model(model_type)
                params_obj = model.Params(**fitted_params)
                fitted_trace = model.eval(time_data, params_obj)

                lines_data.append((time_data, fitted_trace))
                styles_data.append(
                    {"color": "red", "alpha": 0.8, "label": "Fitted", "linewidth": 2}
                )
            except Exception as e:
                logger.warning(
                    f"Could not generate fitted curve for cell {cell_id}: {e}"
                )

        # Prepare title
        title_parts = [f"Trace: {cell_id}"]
        if model_type:
            title_parts.append(f"Model: {model_type}")
        if r_squared is not None:
            title_parts.append(f"R²: {r_squared:.3f}")
        title = " | ".join(title_parts)

        self._render_trace_plot_internal(
            lines_data,
            styles_data,
            title=title,
            x_label="Time (hours)",
            y_label="Intensity",
        )

    def _render_trace_plot_internal(
        self,
        lines_data: list,
        styles_data: list,
        *,
        title: str = "",
        x_label: str = "Time (hours)",
        y_label: str = "Intensity",
    ) -> None:
        """Internal method to render the trace plot."""
        cached_payload = (tuple(map(repr, lines_data)), tuple(map(repr, styles_data)))
        new_hash = hashlib.md5(repr(cached_payload).encode()).hexdigest()

        if new_hash == self._last_plot_hash and title == self._current_title:
            return

        self._trace_canvas.plot_lines(
            lines_data,
            styles_data,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
        self._last_plot_hash = new_hash
        self._current_title = title
