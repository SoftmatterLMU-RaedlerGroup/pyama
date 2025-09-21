"""
Fitting panel widget for batch fitting controls.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QLabel,
    QMessageBox,
    QProgressBar,
)
from PySide6.QtCore import Signal, Slot
from pathlib import Path
import numpy as np
import pandas as pd

from pyama_qt.widgets import MplCanvas, ParameterPanel
from pyama_core.analysis.models import get_model, get_types
from pyama_core.analysis.fitting import get_trace


class FittingPanel(QWidget):
    """Middle panel widget with fitting controls and quality control."""

    fitting_requested = Signal(Path, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Group 1: Fitting
        fitting_group = QGroupBox("Fitting")
        fitting_layout = QVBoxLayout(fitting_group)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["Trivial", "Maturation"])
        self.model_combo.currentTextChanged.connect(self.update_model_params)
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        fitting_layout.addLayout(model_layout)

        self.param_panel = ParameterPanel()
        fitting_layout.addWidget(self.param_panel)

        self.update_model_params()

        self.start_fitting_btn = QPushButton("Start Fitting")
        self.start_fitting_btn.clicked.connect(self.start_fitting_clicked)
        self.start_fitting_btn.setEnabled(False)
        fitting_layout.addWidget(self.start_fitting_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        fitting_layout.addWidget(self.progress_bar)

        layout.addWidget(fitting_group, 1)

        # Group 2: Quality Check
        qc_group = QGroupBox("Quality Check")
        qc_layout = QVBoxLayout(qc_group)
        cell_layout = QHBoxLayout()
        cell_layout.addWidget(QLabel("Cell ID:"))
        self.cell_id_input = QLineEdit()
        self.cell_id_input.setPlaceholderText("Enter cell ID (fov_xxx_cell_xxx)")
        cell_layout.addWidget(self.cell_id_input)
        qc_layout.addLayout(cell_layout)
        btn_layout = QHBoxLayout()
        self.visualize_btn = QPushButton("Visualize")
        self.visualize_btn.clicked.connect(self.visualize_clicked)
        self.visualize_btn.setEnabled(False)
        btn_layout.addWidget(self.visualize_btn)
        self.shuffle_btn = QPushButton("Shuffle")
        self.shuffle_btn.clicked.connect(self.shuffle_clicked)
        self.shuffle_btn.setEnabled(False)
        btn_layout.addWidget(self.shuffle_btn)
        qc_layout.addLayout(btn_layout)
        self.qc_canvas = MplCanvas(self, width=5, height=3)
        qc_layout.addWidget(self.qc_canvas)

        layout.addWidget(qc_group, 1)

    @Slot()
    def update_model_params(self):
        model_type = self.model_combo.currentText().lower()
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
        except (ValueError, AttributeError):
            df = pd.DataFrame()
        self.param_panel.set_parameters_df(df)

    @Slot()
    def start_fitting_clicked(self):
        if self.main_window.raw_csv_path is None:
            QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return
        model_type = self.model_combo.currentText().lower()
        params_df = self.param_panel.get_values_df()
        # Convert DataFrame to legacy dicts required by the fitting backend
        model_params: dict = {}
        model_bounds: dict = {}
        if params_df is not None and not params_df.empty:
            # value/min/max mapping if present
            if "value" in params_df.columns:
                model_params = params_df["value"].to_dict()
            else:
                # If no explicit 'value', take the first column
                first_col = params_df.columns[0]
                model_params = params_df[first_col].to_dict()
            if "min" in params_df.columns and "max" in params_df.columns:
                for name, row in params_df.iterrows():
                    min_v = row.get("min")
                    max_v = row.get("max")
                    if pd.notna(min_v) and pd.notna(max_v):
                        try:
                            model_bounds[name] = (float(min_v), float(max_v))
                        except Exception:
                            pass
        fitting_params = {
            "model_params": model_params,
            "model_bounds": model_bounds,
        }
        self.fitting_requested.emit(
            self.main_window.raw_csv_path,
            {
                "model_type": model_type,
                "fitting_params": fitting_params,
                "data_format": "simple",
            },
        )

    @Slot()
    def visualize_clicked(self):
        cell_name = self.cell_id_input.text().strip()
        if not cell_name:
            return
        self._visualize_by_name(cell_name)

    @Slot()
    def shuffle_clicked(self):
        if self.main_window.raw_data is None:
            return
        # Choose random column index and get its name
        random_index = np.random.randint(0, len(self.main_window.raw_data.columns))
        cell_name = self.main_window.raw_data.columns[random_index]
        self.cell_id_input.setText(cell_name)
        self._visualize_by_index(random_index, cell_name)

    def _visualize_by_name(self, cell_name: str):
        """User entered cell name -> find index -> visualize."""
        try:
            cell_index = list(self.main_window.raw_data.columns).index(cell_name)
            self._visualize_by_index(cell_index, cell_name)
        except ValueError:
            QMessageBox.warning(
                self, "Cell Not Found", f"Cell '{cell_name}' not found in data."
            )

    def _visualize_by_index(self, cell_index: int, cell_name: str):
        """Core visualization: get data and fit using index, display using name."""
        # Get data using integer index
        time_data, intensity_data = get_trace(self.main_window.raw_data, cell_index)

        lines_data = [(time_data, intensity_data)]
        styles_data = [
            {
                "plot_style": "scatter",
                "color": "blue",
                "alpha": 0.6,
                "s": 20,
                "label": f"{cell_name} (data)",
            }
        ]

        # Add fitted curve if available
        self._add_fitted_curve(cell_index, time_data, lines_data, styles_data)
        self.qc_canvas.plot_lines(
            lines_data,
            styles_data,
            title=f"Quality Control - {cell_name}",
            x_label="Time",
            y_label="Intensity",
        )

    def _add_fitted_curve(self, cell_index: int, time_data, lines_data, styles_data):
        """Add fitted curve to plot if fitting results are available."""
        if (
            self.main_window.fitted_results is None
            or self.main_window.fitted_results.empty
        ):
            return

        # Look up fitting results using integer index
        cell_fit = self.main_window.fitted_results[
            self.main_window.fitted_results["cell_id"] == cell_index
        ]

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
                r_squared = first_fit.get("r_squared", 0)

                lines_data.append((t_smooth, y_fit))
                styles_data.append(
                    {
                        "plot_style": "line",
                        "color": "red",
                        "linewidth": 2,
                        "label": f"Fit (R²={r_squared:.3f})",
                    }
                )
        except (ValueError, AttributeError, KeyError):
            pass

    def set_cell_id(self, cell_name: str):
        self.cell_id_input.setText(cell_name)

    def set_data(self, csv_path: Path, data: pd.DataFrame):
        self.main_window.raw_csv_path = csv_path
        self.main_window.raw_data = data
        self.start_fitting_btn.setEnabled(True)
        self.visualize_btn.setEnabled(True)
        self.shuffle_btn.setEnabled(True)

    def set_fitting_active(self, active: bool):
        self.start_fitting_btn.setEnabled(not active)
        self.model_combo.setEnabled(not active)
        self.param_panel.setEnabled(not active)
        if active:
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.progress_bar.show()
        else:
            self.progress_bar.hide()

    def update_fitting_results(self, results_df: pd.DataFrame):
        self.main_window.fitted_results = results_df
        current_cell_name = self.cell_id_input.text().strip()
        if current_cell_name:
            self._visualize_by_name(current_cell_name)
