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
    QDoubleSpinBox,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QLabel,
    QMessageBox,
    QProgressBar,
)
from PySide6.QtCore import Signal, Slot
from pathlib import Path
import numpy as np
import pandas as pd

from pyama_qt.utils.mpl_canvas import MplCanvas


class FittingPanel(QWidget):
    """Middle panel widget with fitting controls and quality control."""

    # Signals
    fitting_requested = Signal(Path, dict)  # data_path, params

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.param_spinboxes = {}
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)

        # Fitting Parameters Group
        params_group = QGroupBox("Fitting Parameters")
        params_layout = QFormLayout()

        # Model selection
        self.model_combo = QComboBox()
        self.model_combo.addItems(["Trivial", "Maturation"])
        self.model_combo.currentTextChanged.connect(self.update_model_params)
        params_layout.addRow("Model:", self.model_combo)

        # Create parameter input section that updates based on model
        self.params_widget = QWidget()
        self.params_widget_layout = QFormLayout(self.params_widget)
        params_layout.addRow(self.params_widget)

        # Initialize with default model
        self.update_model_params()

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # Start Batch Fitting button
        self.start_fitting_btn = QPushButton("Start Batch Fitting")
        self.start_fitting_btn.clicked.connect(self.start_fitting_clicked)
        self.start_fitting_btn.setEnabled(False)
        layout.addWidget(self.start_fitting_btn)

        # Progress bar for feedback
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Set to indeterminate (bouncing)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)  # Initially hidden
        layout.addWidget(self.progress_bar)

        # Quality Control Section with visualization
        qc_group = QGroupBox("Quality Control")
        qc_layout = QVBoxLayout()

        # Cell ID input
        cell_layout = QHBoxLayout()
        cell_layout.addWidget(QLabel("Cell ID:"))
        self.cell_id_input = QLineEdit()
        self.cell_id_input.setPlaceholderText("Enter cell ID")
        cell_layout.addWidget(self.cell_id_input)
        qc_layout.addLayout(cell_layout)

        # Buttons
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

        # Add visualization plot for quality control
        self.qc_canvas = MplCanvas(self, width=5, height=3)
        qc_layout.addWidget(self.qc_canvas)

        # Initialize QC plot
        self.qc_ax = self.qc_canvas.fig.add_subplot(111)
        self.qc_ax.set_xlabel("Time")
        self.qc_ax.set_ylabel("Intensity")
        self.qc_ax.set_title("Quality Control Visualization")
        self.qc_ax.grid(True, alpha=0.3)
        self.qc_canvas.draw()

        qc_group.setLayout(qc_layout)
        layout.addWidget(qc_group)

        layout.addStretch()

    @Slot()
    def update_model_params(self):
        """Update parameter inputs based on selected model."""
        # Clear existing parameters
        for widget in list(self.param_spinboxes.values()):
            widget.deleteLater()
        self.param_spinboxes.clear()

        # Clear layout
        while self.params_widget_layout.count():
            item = self.params_widget_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        model_type = self.model_combo.currentText().lower()

        # Add checkbox to enable/disable manual parameter setting
        self.use_manual_params = QCheckBox("Set initial parameters manually")
        self.use_manual_params.stateChanged.connect(self.toggle_param_inputs)
        self.params_widget_layout.addRow(self.use_manual_params)

        if model_type == "maturation":
            # Maturation model parameters
            params = {
                "ktl": (1.0, 5e8, None, 100.0),  # min, max, placeholder, step
                "km": (1e-5, 30.0, 1.28, 0.01),
                "beta": (1e-5, 10.0, 5.22e-3, 0.001),
                "delta": (1e-5, 11.0, 0.01, 0.001),
            }
        elif model_type == "trivial":
            # Trivial model parameters
            params = {
                "ktl": (1.0, 5e4, None, 1.0),
                "beta": (1e-5, 10.0, 0.0436, 0.001),
                "delta": (1e-5, 10.1, 0.07, 0.001),
            }
        else:
            params = {}

        # Create spinboxes for each parameter
        for param_name, (min_val, max_val, placeholder, step) in params.items():
            label = QLabel(f"{param_name}:")
            spinbox = QDoubleSpinBox()
            spinbox.setRange(min_val, max_val)
            spinbox.setSingleStep(step)
            spinbox.setDecimals(6)
            spinbox.setSpecialValueText("Auto")
            spinbox.setValue(min_val)  # Set to minimum to show "Auto"
            spinbox.setEnabled(False)  # Initially disabled

            # Store placeholder value for reference
            if placeholder is not None:
                spinbox.setToolTip(f"Default: {placeholder}")

            self.param_spinboxes[param_name] = spinbox
            self.params_widget_layout.addRow(label, spinbox)

        # Note about automatic parameters
        info_label = QLabel("Note: t0 and offset are automatically estimated from data")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        self.params_widget_layout.addRow(info_label)

    @Slot()
    def toggle_param_inputs(self):
        """Enable/disable parameter input fields."""
        enabled = self.use_manual_params.isChecked()
        for spinbox in self.param_spinboxes.values():
            spinbox.setEnabled(enabled)
            if enabled and spinbox.value() == spinbox.minimum():
                # Set to a reasonable default when enabling
                tooltip = spinbox.toolTip()
                if tooltip.startswith("Default: "):
                    try:
                        default_val = float(tooltip.replace("Default: ", ""))
                        spinbox.setValue(default_val)
                    except (ValueError, AttributeError):
                        pass

    @Slot()
    def start_fitting_clicked(self):
        """Handle Start Batch Fitting button click."""
        if self.main_window.raw_csv_path is None:
            QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        # Prepare fitting parameters
        model_type = self.model_combo.currentText().lower()

        # Collect initial parameters only if manual mode is enabled
        init_params = {}
        if hasattr(self, "use_manual_params") and self.use_manual_params.isChecked():
            for param_name, spinbox in self.param_spinboxes.items():
                # Only add parameter if it's not at minimum ("Auto" value)
                if spinbox.value() != spinbox.minimum():
                    init_params[param_name] = spinbox.value()

        # Empty dict means use model's automatic parameter estimation
        fitting_params = {
            "model_params": init_params,
        }

        # Emit signal to start fitting
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
        """Handle Visualize button click to show cell in local plot."""
        cell_id = self.cell_id_input.text().strip()
        if not cell_id:
            QMessageBox.warning(self, "No Cell ID", "Please enter a cell ID.")
            return

        self.visualize_cell(cell_id)

    @Slot()
    def shuffle_clicked(self):
        """Handle Shuffle button click to select random cell."""
        if self.main_window.raw_data is None:
            return

        cell_ids = self.main_window.raw_data["cell_id"].unique()
        random_cell = str(np.random.choice(cell_ids))
        self.cell_id_input.setText(random_cell)
        self.visualize_cell(random_cell)

    def visualize_cell(self, cell_id: str):
        """Visualize a specific cell in the QC plot."""
        if self.main_window.raw_data is None:
            return

        # Check if cell exists
        if cell_id not in self.main_window.raw_data["cell_id"].values:
            QMessageBox.warning(
                self, "Cell Not Found", f"Cell ID '{cell_id}' not found in data."
            )
            return

        # Get cell data
        cell_data = self.main_window.raw_data[self.main_window.raw_data["cell_id"] == cell_id]

        # Clear and update QC plot
        self.qc_ax.clear()

        # Plot the raw data first (underneath)
        self.qc_ax.scatter(
            cell_data["time"].values,
            cell_data["intensity_total"].values,
            color="blue",
            alpha=0.6,
            s=20,
            label=f"Cell {cell_id} (data)",
            zorder=1,  # Draw underneath
        )

        # If we have fitting results, overlay the fit on top
        if self.main_window.fitted_results is not None and not self.main_window.fitted_results.empty:
            # Try to find this cell in the fitting results (handle both string and int cell_id)
            cell_fit = self.main_window.fitted_results[
                (self.main_window.fitted_results["cell_id"] == cell_id) | 
                (self.main_window.fitted_results["cell_id"].astype(str) == str(cell_id))
            ]
            
            if not cell_fit.empty and cell_fit.iloc[0]["success"]:
                # Get the model type and parameters
                model_type = cell_fit.iloc[0].get("model_type", "unknown")
                
                # Reconstruct the fitted curve using the model
                from pyama_qt.analysis.models.maturation import MaturationModel
                from pyama_qt.analysis.models.trivial import TrivialModel
                
                # Select the appropriate model
                if model_type.lower() in ["maturation", "threestage"]:
                    model = MaturationModel({})
                elif model_type.lower() == "trivial":
                    model = TrivialModel({})
                else:
                    model = None
                
                if model is not None:
                    # Get the fitted parameters
                    param_names = model.get_params()
                    params = []
                    for param_name in param_names:
                        if param_name in cell_fit.columns:
                            params.append(float(cell_fit.iloc[0][param_name]))
                    
                    if params:
                        # Generate smooth curve for visualization
                        t_smooth = np.linspace(
                            cell_data["time"].min(),
                            cell_data["time"].max(),
                            200
                        )
                        y_fit = model.eval_fit(t_smooth, *params)
                        
                        # Plot the fitted curve on top
                        self.qc_ax.plot(
                            t_smooth,
                            y_fit,
                            color="red",
                            linewidth=2,
                            label=f"Fit (χ²={cell_fit.iloc[0].get('chisq', 0):.2e})",
                            zorder=2,  # Draw on top
                        )

        self.qc_ax.set_xlabel("Time")
        self.qc_ax.set_ylabel("Intensity")
        self.qc_ax.set_title(f"Quality Control - Cell {cell_id}")
        self.qc_ax.grid(True, alpha=0.3)
        self.qc_ax.legend()

        self.qc_canvas.draw()

    def set_cell_id(self, cell_id: str):
        """Set the cell ID in the input field."""
        self.cell_id_input.setText(cell_id)

    def set_data(self, csv_path: Path, data: pd.DataFrame):
        """Set the current data path and dataframe, and enable controls."""
        self.main_window.raw_csv_path = csv_path
        self.main_window.raw_data = data
        self.start_fitting_btn.setEnabled(True)
        self.visualize_btn.setEnabled(True)
        self.shuffle_btn.setEnabled(True)

    def set_fitting_active(self, active: bool):
        """Enable or disable controls during fitting and show/hide progress bar."""
        self.start_fitting_btn.setEnabled(not active)
        self.model_combo.setEnabled(not active)
        self.use_manual_params.setEnabled(not active)
        # Show/hide and animate progress bar
        self.progress_bar.setVisible(active)
    
    def update_fitting_results(self, results_df: pd.DataFrame):
        """Update the stored fitting results."""
        self.main_window.fitted_results = results_df
        
        # If a cell is currently displayed, refresh the visualization
        current_cell = self.cell_id_input.text().strip()
        if current_cell:
            self.visualize_cell(current_cell)
