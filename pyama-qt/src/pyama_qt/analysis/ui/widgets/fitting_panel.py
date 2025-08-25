'''
Fitting panel widget for batch fitting controls.
'''

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
)
from PySide6.QtCore import Signal, Slot
from pathlib import Path
import numpy as np
import pandas as pd

from pyama_qt.widgets.mpl_canvas import MplCanvas
from pyama_qt.analysis.models import get_model, get_types
<<<<<<< Updated upstream
<<<<<<< Updated upstream
from pyama_core.analysis.utils.load_data import get_trace
=======
from pyama_qt.widgets.parameter_panel import ParameterPanel
from pyama_qt.widgets.progress_indicator import ProgressIndicator
>>>>>>> Stashed changes
=======
from pyama_qt.widgets.parameter_panel import ParameterPanel
from pyama_qt.widgets.progress_indicator import ProgressIndicator
>>>>>>> Stashed changes


class FittingPanel(QWidget):
    """Middle panel widget with fitting controls and quality control."""

    fitting_requested = Signal(Path, dict)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Group 1: Fitting
        fitting_group = QGroupBox("Fitting")
        fitting_layout = QVBoxLayout(fitting_group)

        model_layout = QFormLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItems(["Trivial", "Maturation"])
        self.model_combo.currentTextChanged.connect(self.update_model_params)
        model_layout.addRow("Model:", self.model_combo)
        fitting_layout.addLayout(model_layout)

        self.param_panel = ParameterPanel()
        fitting_layout.addWidget(self.param_panel)

        self.update_model_params()

        self.start_fitting_btn = QPushButton("Start Fitting")
        self.start_fitting_btn.clicked.connect(self.start_fitting_clicked)
        self.start_fitting_btn.setEnabled(False)
        fitting_layout.addWidget(self.start_fitting_btn)

        self.progress_indicator = ProgressIndicator()
        fitting_layout.addWidget(self.progress_indicator)

        layout.addWidget(fitting_group)

        # Group 2: Quality Check
        qc_group = QGroupBox("Quality Check")
        qc_layout = QVBoxLayout(qc_group)
        cell_layout = QHBoxLayout()
        cell_layout.addWidget(QLabel("Cell ID:"))
        self.cell_id_input = QLineEdit()
        self.cell_id_input.setPlaceholderText("Enter cell ID")
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
        qc_group.setLayout(qc_layout)
        layout.addWidget(qc_group)

    @Slot()
    def update_model_params(self):
        model_type = self.model_combo.currentText().lower()
        param_defs = []
        try:
            model = get_model(model_type)
            types = get_types(model_type)
            UserParams = types['UserParams']
            user_param_names = list(UserParams.__annotations__.keys())
            for param_name in user_param_names:
                default_val = model.DEFAULTS[param_name]
                min_val, max_val = model.BOUNDS[param_name]
                param_defs.append({
                    "name": param_name, "label": f"{param_name}:", "type": "float",
                    "default": default_val, "min": min_val, "max": max_val, "show_bounds": True
                })
        except (ValueError, AttributeError):
            pass
        self.param_panel.set_parameters(param_defs)

    @Slot()
    def start_fitting_clicked(self):
        if self.main_window.raw_csv_path is None:
            QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return
        model_type = self.model_combo.currentText().lower()
        param_values = self.param_panel.get_values()
        fitting_params = {"model_params": param_values["params"], "model_bounds": param_values["bounds"]}
        self.fitting_requested.emit(
            self.main_window.raw_csv_path,
            {"model_type": model_type, "fitting_params": fitting_params, "data_format": "simple"},
        )

    @Slot()
    def visualize_clicked(self):
        cell_id_text = self.cell_id_input.text().strip()
        if not cell_id_text: return
        try:
            cell_id = int(cell_id_text)
            self.visualize_cell(cell_id)
        except ValueError:
            QMessageBox.warning(self, "Invalid Cell ID", "Cell ID must be a number.")

    @Slot()
    def shuffle_clicked(self):
        if self.main_window.raw_data is None: return
        random_cell = np.random.choice(self.main_window.raw_data.columns)
        self.cell_id_input.setText(str(random_cell))
        self.visualize_cell(random_cell)

    def visualize_cell(self, cell_id: int):
<<<<<<< Updated upstream
<<<<<<< Updated upstream
        """Visualize a specific cell in the QC plot."""
        if self.main_window.raw_data is None:
            return

        # Use positional index directly; raw_data has unlabeled columns
        try:
            cell_id = int(cell_id)
        except Exception:
            QMessageBox.warning(
                self, "Cell Not Found", f"Cell id '{cell_id}' cannot be resolved."
            )
            return

        # Validate positional index
        if not (0 <= cell_id < self.main_window.raw_data.shape[1]):
            QMessageBox.warning(
                self, "Cell Not Found", f"Cell index '{cell_id}' is out of range."
            )
            return

        # Use shared helper to extract time and intensity by positional index
        time_data, intensity_data = get_trace(self.main_window.raw_data, int(cell_id))
=======
        if self.main_window.raw_data is None: return
        if cell_id not in self.main_window.raw_data.columns:
            QMessageBox.warning(self, "Cell Not Found", f"Cell ID '{cell_id}' not found in data.")
            return

        time_data = self.main_window.raw_data.index.values
        intensity_data = self.main_window.raw_data[cell_id].values
>>>>>>> Stashed changes

        lines_data = [(time_data, intensity_data)]
        styles_data = [
            {
                "plot_style": "scatter",
                "color": "blue",
                "alpha": 0.6,
                "s": 20,
                "label": f"Cell {cell_id} (data)",
            }
        ]

        if self.main_window.fitted_results is not None and not self.main_window.fitted_results.empty:
<<<<<<< Updated upstream
            # Try to find this cell in the fitting results using positional index
            cell_fit = self.main_window.fitted_results[
                self.main_window.fitted_results["cell_id"] == cell_id
            ]
            
            # Check if the fit was successful before plotting
            if not cell_fit.empty and 'success' in cell_fit.columns and cell_fit.iloc[0]["success"]:
                # Get the model type to reconstruct the fitted curve
=======
            cell_fit = self.main_window.fitted_results[self.main_window.fitted_results["cell_id"] == cell_id]
            if not cell_fit.empty and cell_fit.iloc[0].get("success"):
>>>>>>> Stashed changes
=======
        if self.main_window.raw_data is None: return
        if cell_id not in self.main_window.raw_data.columns:
            QMessageBox.warning(self, "Cell Not Found", f"Cell ID '{cell_id}' not found in data.")
            return

        time_data = self.main_window.raw_data.index.values
        intensity_data = self.main_window.raw_data[cell_id].values

        lines_data = [(time_data, intensity_data)]
        styles_data = [
            {
                "plot_style": "scatter",
                "color": "blue",
                "alpha": 0.6,
                "s": 20,
                "label": f"Cell {cell_id} (data)",
            }
        ]

        if self.main_window.fitted_results is not None and not self.main_window.fitted_results.empty:
            cell_fit = self.main_window.fitted_results[self.main_window.fitted_results["cell_id"] == cell_id]
            if not cell_fit.empty and cell_fit.iloc[0].get("success"):
>>>>>>> Stashed changes
                model_type = cell_fit.iloc[0].get("model_type", "").lower()
                try:
                    model = get_model(model_type)
                    param_names = list(model.DEFAULTS.keys())
                    params_dict = {p: float(cell_fit.iloc[0][p]) for p in param_names if p in cell_fit.columns and pd.notna(cell_fit.iloc[0][p])}
                    if len(params_dict) == len(param_names):
                        t_smooth = np.linspace(time_data.min(), time_data.max(), 200)
                        y_fit = model.eval(t_smooth, params_dict)
                        r_squared = cell_fit.iloc[0].get('r_squared', 0)
                        lines_data.append((t_smooth, y_fit))
                        styles_data.append(
                            {
                                "plot_style": "line",
                                "color": "red",
                                "linewidth": 2,
                                "label": f"Fit (R²={r_squared:.3f})",
                            }
                        )
                except (ValueError, AttributeError):
                    pass

        self.qc_canvas.plot_lines(
            lines_data,
            styles_data,
            title=f"Quality Control - Cell {cell_id}",
            x_label="Time",
            y_label="Intensity",
        )

    def set_cell_id(self, cell_id: int | str):
        self.cell_id_input.setText(str(cell_id))

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
            self.progress_indicator.task_started("Fitting in progress...")
        else:
            self.progress_indicator.task_finished("Fitting complete.")

    def update_fitting_results(self, results_df: pd.DataFrame):
        self.main_window.fitted_results = results_df
        current_cell_text = self.cell_id_input.text().strip()
        if current_cell_text:
            try:
                self.visualize_cell(int(current_cell_text))
            except ValueError:
                pass
