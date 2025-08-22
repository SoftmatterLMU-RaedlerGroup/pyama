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
from pathlib import Path

from pyama_qt.utils.mpl_canvas import MplCanvas


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
        # Data is now stored centrally in MainWindow
        if self.main_window:
            self.main_window.fitted_results = results_df

        # Update quality plot
        self.quality_ax.clear()

        fitted_results = self.main_window.fitted_results if self.main_window else None
        
        if fitted_results is not None and "chisq" in fitted_results.columns:
            chisq_values = fitted_results["chisq"].values
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
        if fitted_results is not None and len(fitted_results) > 0:
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
            for col in fitted_results.columns:
                if col not in metadata_cols:
                    # Check if column contains numeric data
                    try:
                        pd.to_numeric(fitted_results[col], errors='coerce').dropna()
                        if pd.to_numeric(fitted_results[col], errors='coerce').notna().any():
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
        if fitted_results is None:
            return

        self.param_ax.clear()

        # Check if parameter exists in results
        if param_name in fitted_results.columns:
            # Get values and convert to numeric, dropping non-numeric values
            series = pd.to_numeric(fitted_results[param_name], errors='coerce')
            values = series.dropna().values

            if len(values) > 0:
                # Calculate robust range using percentiles to exclude outliers
                percentiles = np.percentile(values, [10, 90])
                if hasattr(percentiles, '__len__') and len(percentiles) == 2:
                    p10, p90 = float(percentiles[0]), float(percentiles[1])
                else:
                    p10, p90 = np.min(values), np.max(values)
                
                # Use robust range (10th to 90th percentile) instead of full min/max
                robust_range = p90 - p10
                
                # Use fixed 30 bins now that outliers are excluded
                n_bins = 30
                
                # Create bins based on robust range, but extend slightly to include more data
                hist_min = max(np.min(values), p10 - 0.1 * robust_range)
                hist_max = min(np.max(values), p90 + 0.1 * robust_range)
                
                # Create histogram with robust range
                counts, _, patches = self.param_ax.hist(
                    values, bins=n_bins, range=(hist_min, hist_max), 
                    alpha=0.7, color="blue", edgecolor="black"
                )
                
                # Highlight the peak region with different colors
                max_count = np.max(counts)
                threshold = max_count * 0.8  # 80% of peak height
                
                for count, patch in zip(counts, patches):
                    if count >= threshold:
                        patch.set_facecolor('orange')
                        patch.set_alpha(0.9)

                # Calculate statistics for display
                mean_val = np.mean(values)
                median_val = np.median(values)
                std_val = np.std(values)
                
                # Count outliers
                outliers = values[(values < p10) | (values > p90)]
                n_outliers = len(outliers)
                
                # Add text box with detailed statistics including outlier info
                stats_text = f"N: {len(values)}\nMean: {mean_val:.3f}\nMedian: {median_val:.3f}\nStd: {std_val:.3f}"
                if n_outliers > 0:
                    stats_text += f"\nOutliers: {n_outliers} ({100*n_outliers/len(values):.1f}%)"
                
                self.param_ax.text(0.02, 0.98, stats_text, transform=self.param_ax.transAxes,
                                 verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
                
                # Set plot limits to 10th-90th percentile range
                self.param_ax.set_xlim(p10, p90)

        self.param_ax.set_xlabel(f"{param_name} Value")
        self.param_ax.set_ylabel("Count")
        self.param_ax.set_title(f"{param_name} Distribution")
        self.param_ax.grid(True, alpha=0.3)
        self.param_canvas.draw()

        # Emit signal
        self.parameter_selected.emit(param_name)
