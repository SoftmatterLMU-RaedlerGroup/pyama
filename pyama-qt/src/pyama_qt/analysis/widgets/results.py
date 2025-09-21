"""
Quality panel widget for displaying fitting results and quality metrics.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QGroupBox,
    QCheckBox,
)
from PySide6.QtCore import Signal, Slot
import pandas as pd
import logging

from pyama_qt.widgets import MplCanvas

logger = logging.getLogger(__name__)


class ResultsPanel(QWidget):
    """Right panel widget with fitting results plots and parameter distributions."""

    # Signals
    parameter_selected = Signal(str)  # param_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent  # Reference to MainWindow for centralized data
        self.filter_good_only = False  # Track filter state
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)

        # Top-level group: Results
        results_group = QGroupBox("Results")
        group_layout = QVBoxLayout(results_group)

        # Fitting Quality Plot
        quality_label = QLabel("Fitting Quality")
        group_layout.addWidget(quality_label)

        self.quality_canvas = MplCanvas(self, width=5, height=4)
        group_layout.addWidget(self.quality_canvas)

        # Parameter selection dropdown and filter button
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("Parameter:"))
        self.param_combo = QComboBox()
        self.param_combo.addItems(["t0", "ktl", "delta", "beta", "offset"])
        self.param_combo.currentTextChanged.connect(self.update_param_histogram)
        param_layout.addWidget(self.param_combo)

        # Filter checkbox
        self.filter_checkbox = QCheckBox("Good Fits Only")
        self.filter_checkbox.setChecked(False)
        self.filter_checkbox.stateChanged.connect(self.toggle_filter)
        param_layout.addWidget(self.filter_checkbox)

        param_layout.addStretch()
        group_layout.addLayout(param_layout)

        # Parameter Histogram Plot
        self.param_canvas = MplCanvas(self, width=5, height=4)
        group_layout.addWidget(self.param_canvas)

        layout.addWidget(results_group)

    def update_fitting_results(self, results_df: pd.DataFrame):
        """Update plots with fitting results."""
        # Data is now stored centrally in MainWindow (keep all data including failures)
        if self.main_window:
            self.main_window.fitted_results = results_df

        # Update quality plot
        if results_df is not None:
            r_squared_values = results_df.get(
                "r_squared", pd.Series(dtype=float)
            ).values
            if len(r_squared_values) > 0:
                # Calculate percentages for each quality category
                total_count = len(r_squared_values)
                good_count = sum(1 for r2 in r_squared_values if r2 > 0.9)
                fair_count = sum(1 for r2 in r_squared_values if 0.7 < r2 <= 0.9)
                poor_count = sum(1 for r2 in r_squared_values if r2 <= 0.7)

                good_pct = (good_count / total_count) * 100 if total_count > 0 else 0
                fair_pct = (fair_count / total_count) * 100 if total_count > 0 else 0
                poor_pct = (poor_count / total_count) * 100 if total_count > 0 else 0

                colors = [
                    "green" if r2 > 0.9 else "orange" if r2 > 0.7 else "red"
                    for r2 in r_squared_values
                ]
                lines_data = [(range(len(r_squared_values)), r_squared_values)]
                styles_data = [
                    {
                        "plot_style": "scatter",
                        "color": colors,
                        "alpha": 0.6,
                        "s": 20,
                    }
                ]

                # Create legend text with percentages
                legend_text = f"Good (R²>0.9): {good_pct:.1f}%\nFair (0.7<R²≤0.9): {fair_pct:.1f}%\nPoor (R²≤0.7): {poor_pct:.1f}%"

                self.quality_canvas.plot_lines(
                    lines_data,
                    styles_data,
                    title="Fitting Quality",
                    x_label="Cell Index",
                    y_label="R² (Coefficient of Determination)",
                )

                # Add legend text box after plotting
                ax = self.quality_canvas.axes
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

        # Update parameter combo box with actual fitted parameters
        if results_df is not None and len(results_df) > 0:
            # Get parameter columns (exclude metadata columns and non-numeric columns)
            metadata_cols = [
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
            ]

            # Filter for numeric columns only
            param_cols = []
            for col in results_df.columns:
                if col not in metadata_cols:
                    # Check if column contains numeric data
                    try:
                        pd.to_numeric(results_df[col], errors="coerce").dropna()
                        if (
                            pd.to_numeric(results_df[col], errors="coerce")
                            .notna()
                            .any()
                        ):
                            param_cols.append(col)
                    except Exception:
                        pass

            current_text = self.param_combo.currentText()
            self.param_combo.clear()
            if param_cols:
                self.param_combo.addItems(param_cols)
                # Try to restore previous selection
                if current_text in param_cols:
                    self.param_combo.setCurrentText(current_text)

        # Update parameter histogram
        self.update_param_histogram(self.param_combo.currentText())

    @Slot()
    def toggle_filter(self):
        """Toggle the filter for good fits only."""
        self.filter_good_only = self.filter_checkbox.isChecked()
        self.update_param_histogram(self.param_combo.currentText())

    @Slot(str)
    def update_param_histogram(self, param_name: str):
        """Update parameter histogram based on selection."""
        fitted_results = self.main_window.fitted_results if self.main_window else None
        if fitted_results is None or param_name not in fitted_results.columns:
            self.param_canvas.clear()
            return

        # Apply filter if enabled
        data_to_plot = fitted_results
        if self.filter_good_only and "r_squared" in fitted_results.columns:
            # Filter for good fits only (R² > 0.9)
            data_to_plot = fitted_results[fitted_results["r_squared"] > 0.9]

        values = (
            pd.to_numeric(data_to_plot[param_name], errors="coerce").dropna().values
        )

        # Update title to indicate filtering
        title = f"{param_name} Distribution"
        if self.filter_good_only:
            title += " (Good Fits Only)"

        if len(values) > 0:
            self.param_canvas.plot_histogram(
                values,
                bins=30,
                title=title,
                x_label=f"{param_name} Value",
                y_label="Count",
            )
        else:
            self.param_canvas.clear()

        # Emit signal
        self.parameter_selected.emit(param_name)
