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
)
from PySide6.QtCore import Signal, Slot
import numpy as np
import pandas as pd

from pyama_qt.widgets.mpl_canvas import MplCanvas


class ResultsPanel(QWidget):
    """Right panel widget with fitting results plots and parameter distributions."""

    # Signals
    parameter_selected = Signal(str)  # param_name

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window  # Reference to MainWindow for centralized data
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)

        # Top-level group: Results
        results_group = QGroupBox("Results")
        group_layout = QVBoxLayout()

        # Fitting Quality Plot
        quality_label = QLabel("Fitting Quality")
        group_layout.addWidget(quality_label)

        self.quality_canvas = MplCanvas(self, width=5, height=4)
        group_layout.addWidget(self.quality_canvas)

        # Parameter selection dropdown
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("Parameter:"))
        self.param_combo = QComboBox()
        self.param_combo.addItems(["t0", "ktl", "delta", "beta", "offset"])
        self.param_combo.currentTextChanged.connect(self.update_param_histogram)
        param_layout.addWidget(self.param_combo)
        param_layout.addStretch()
        group_layout.addLayout(param_layout)

        # Parameter Histogram Plot
        self.param_canvas = MplCanvas(self, width=5, height=4)
        group_layout.addWidget(self.param_canvas)

        results_group.setLayout(group_layout)
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
                self.quality_canvas.plot_lines(
                    lines_data,
                    styles_data,
                    title="Fitting Quality",
                    x_label="Cell Index",
                    y_label="R² (Coefficient of Determination)",
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
                    except:
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

    @Slot(str)
    def update_param_histogram(self, param_name: str):
        """Update parameter histogram based on selection."""
        fitted_results = self.main_window.fitted_results if self.main_window else None
        if fitted_results is None or param_name not in fitted_results.columns:
            self.param_canvas.clear()
            return

        values = (
            pd.to_numeric(fitted_results[param_name], errors="coerce").dropna().values
        )
        if len(values) > 0:
            self.param_canvas.plot_histogram(
                values,
                bins=30,
                title=f"{param_name} Distribution",
                x_label=f"{param_name} Value",
                y_label="Count",
            )
        else:
            self.param_canvas.clear()

        # Emit signal
        self.parameter_selected.emit(param_name)
