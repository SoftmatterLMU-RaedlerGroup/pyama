"""
Quality panel widget for displaying fitting results and quality metrics.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
)
from PySide6.QtCore import Qt, Signal, Slot
import numpy as np
import pandas as pd

from pyama_qt.utils.mpl_canvas import MplCanvas


class ResultsPanel(QWidget):
    """Right panel widget with fitting results plots and parameter distributions."""

    # Signals
    parameter_selected = Signal(str)  # param_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fitting_results = None
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)

        # Fitting Quality Plot
        quality_label = QLabel("Fitting Quality")
        quality_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(quality_label)

        self.quality_canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self.quality_canvas)

        # Initialize quality plot
        self.quality_ax = self.quality_canvas.fig.add_subplot(111)
        self.quality_ax.set_xlabel("Cell Index")
        self.quality_ax.set_ylabel("χ² (Chi-squared)")
        self.quality_ax.set_title("Fitting Quality")
        self.quality_ax.grid(True, alpha=0.3)
        self.quality_canvas.draw()

        # Parameter selection dropdown
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("Parameter:"))
        self.param_combo = QComboBox()
        self.param_combo.addItems(["t0", "ktl", "delta", "beta", "offset"])
        self.param_combo.currentTextChanged.connect(self.update_param_histogram)
        param_layout.addWidget(self.param_combo)
        param_layout.addStretch()
        layout.addLayout(param_layout)

        # Parameter Histogram Plot
        self.param_canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self.param_canvas)

        # Initialize parameter histogram
        self.param_ax = self.param_canvas.fig.add_subplot(111)
        self.param_ax.set_xlabel("Value")
        self.param_ax.set_ylabel("Count")
        self.param_ax.set_title("Parameter Distribution")
        self.param_ax.grid(True, alpha=0.3)
        self.param_canvas.draw()

        layout.addStretch()

    def update_fitting_results(self, results_df: pd.DataFrame):
        """Update plots with fitting results."""
        self.fitting_results = results_df

        # Update quality plot
        self.quality_ax.clear()

        if "chisq" in results_df.columns:
            chisq_values = results_df["chisq"].values
            self.quality_ax.scatter(
                range(len(chisq_values)), chisq_values, alpha=0.6, s=10
            )
            # Note: Lower chi-squared is better, so we might want a different reference line
            # For now, just showing the data without a reference line

        self.quality_ax.set_xlabel("Cell Index")
        self.quality_ax.set_ylabel("χ² (Chi-squared)")
        self.quality_ax.set_title("Fitting Quality")
        self.quality_ax.grid(True, alpha=0.3)
        self.quality_ax.legend()
        self.quality_canvas.draw()

        # Update parameter combo box with actual fitted parameters
        if self.fitting_results is not None and len(self.fitting_results) > 0:
            # Get parameter columns (exclude metadata columns and non-numeric columns)
            metadata_cols = [
                "fov",
                "cell_id",
                "model_type",
                "success",
                "residual_sum_squares",
                "message",
                "n_function_calls",
                "chisq",
                "std",
            ]
            
            # Filter for numeric columns only
            param_cols = []
            for col in self.fitting_results.columns:
                if col not in metadata_cols:
                    # Check if column contains numeric data
                    try:
                        pd.to_numeric(self.fitting_results[col], errors='coerce').dropna()
                        if pd.to_numeric(self.fitting_results[col], errors='coerce').notna().any():
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
        if self.fitting_results is None:
            return

        self.param_ax.clear()

        # Check if parameter exists in results
        if param_name in self.fitting_results.columns:
            # Get values and convert to numeric, dropping non-numeric values
            series = pd.to_numeric(self.fitting_results[param_name], errors='coerce')
            values = series.dropna().values

            if len(values) > 0:
                # Create histogram
                self.param_ax.hist(
                    values, bins=30, alpha=0.7, color="blue", edgecolor="black"
                )

                # Add mean line
                mean_val = np.mean(values)
                self.param_ax.axvline(
                    mean_val, color="red", linestyle="--", label=f"Mean: {mean_val:.2f}"
                )
                self.param_ax.legend()

        self.param_ax.set_xlabel(f"{param_name} Value")
        self.param_ax.set_ylabel("Count")
        self.param_ax.set_title(f"{param_name} Distribution")
        self.param_ax.grid(True, alpha=0.3)
        self.param_canvas.draw()

        # Emit signal
        self.parameter_selected.emit(param_name)
