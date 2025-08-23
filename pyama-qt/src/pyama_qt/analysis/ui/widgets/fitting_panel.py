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
from pyama_qt.analysis.models import get_model, get_types


class FittingPanel(QWidget):
    """Middle panel widget with fitting controls and quality control."""

    # Signals
    fitting_requested = Signal(Path, dict)  # data_path, params

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.param_inputs = {}
        self.param_bounds_min = {}
        self.param_bounds_max = {}
        self.param_defaults = {}
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)

        # Group 1: Fitting (parameters + start button + progress)
        fitting_group = QGroupBox("Fitting")
        fitting_group_layout = QVBoxLayout()

        # Parameters form inside fitting group
        params_container = QWidget()
        params_layout = QFormLayout(params_container)

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

        fitting_group_layout.addWidget(params_container)

        # Start Fitting button
        self.start_fitting_btn = QPushButton("Start Fitting")
        self.start_fitting_btn.clicked.connect(self.start_fitting_clicked)
        self.start_fitting_btn.setEnabled(False)
        fitting_group_layout.addWidget(self.start_fitting_btn)

        # Progress bar for feedback
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Set to indeterminate (bouncing)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)  # Initially hidden
        fitting_group_layout.addWidget(self.progress_bar)

        fitting_group.setLayout(fitting_group_layout)
        layout.addWidget(fitting_group)

        # Group 2: Quality Check (QC section with visualization)
        qc_group = QGroupBox("Quality Check")
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

    @Slot()
    def update_model_params(self):
        """Update parameter inputs based on selected model."""
        # Clear existing parameters
        for widget in list(self.param_inputs.values()):
            widget.deleteLater()
        for widget in list(self.param_bounds_min.values()):
            widget.deleteLater()
        for widget in list(self.param_bounds_max.values()):
            widget.deleteLater()
        self.param_inputs.clear()
        self.param_bounds_min.clear()
        self.param_bounds_max.clear()
        self.param_defaults.clear()

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

        # Get model parameters from the actual model modules
        try:
            model = get_model(model_type)
            types = get_types(model_type)
            
            # Get UserParams and UserBounds types
            UserParams = types['UserParams']
            UserBounds = types['UserBounds']
            
            # Get user-modifiable parameter names from UserParams annotations
            user_param_names = list(UserParams.__annotations__.keys())
            
            # Create input fields for each user-modifiable parameter
            for param_name in user_param_names:
                # Get default from model.DEFAULTS and bounds from model.BOUNDS
                default_val = model.DEFAULTS[param_name]
                min_val, max_val = model.BOUNDS[param_name]
                
                # Create a horizontal layout for parameter value and bounds
                param_layout = QHBoxLayout()
                
                # Parameter value input
                label = QLabel(f"{param_name}:")
                value_edit = QLineEdit()
                value_edit.setEnabled(False)  # Initially disabled
                
                # Bounds inputs (min and max)
                bounds_label = QLabel("Bounds:")
                min_edit = QLineEdit()
                min_edit.setEnabled(False)  # Initially disabled
                min_edit.setMaximumWidth(100)
                
                max_edit = QLineEdit()
                max_edit.setEnabled(False)  # Initially disabled
                max_edit.setMaximumWidth(100)
                
                # Add widgets to horizontal layout
                param_layout.addWidget(value_edit)
                param_layout.addWidget(bounds_label)
                param_layout.addWidget(min_edit)
                param_layout.addWidget(QLabel("-"))
                param_layout.addWidget(max_edit)
                
                # Store default value and bounds for later use
                self.param_defaults[param_name] = {
                    'default': default_val,
                    'min': min_val,
                    'max': max_val
                }
                
                self.param_inputs[param_name] = value_edit
                self.param_bounds_min[param_name] = min_edit
                self.param_bounds_max[param_name] = max_edit
                
                self.params_widget_layout.addRow(label, param_layout)
                
        except (ValueError, AttributeError):
            # Fallback if model not found
            pass

    @Slot()
    def toggle_param_inputs(self):
        """Enable/disable parameter input fields and populate with defaults when enabled."""
        enabled = self.use_manual_params.isChecked()
        
        for param_name, line_edit in self.param_inputs.items():
            line_edit.setEnabled(enabled)
            
            # Also enable/disable bounds fields
            if param_name in self.param_bounds_min:
                self.param_bounds_min[param_name].setEnabled(enabled)
                self.param_bounds_max[param_name].setEnabled(enabled)
            
            if enabled:
                # Populate with default value when enabling (only if empty)
                if param_name in self.param_defaults:
                    default_val = self.param_defaults[param_name]['default']
                    min_val = self.param_defaults[param_name]['min']
                    max_val = self.param_defaults[param_name]['max']
                    
                    # Populate parameter value if empty
                    if line_edit.text() == "":
                        # Format the value nicely
                        if abs(default_val) < 1e-3 or abs(default_val) > 1e4:
                            line_edit.setText(f"{default_val:.6e}")
                        else:
                            line_edit.setText(f"{default_val:.6f}")
                    
                    # Always populate bounds with model.BOUNDS values when enabled
                    if param_name in self.param_bounds_min:
                        self.param_bounds_min[param_name].setText(f"{min_val:.2e}")
                        self.param_bounds_max[param_name].setText(f"{max_val:.2e}")
            else:
                # Clear the fields when disabling
                line_edit.clear()
                if param_name in self.param_bounds_min:
                    self.param_bounds_min[param_name].clear()
                    self.param_bounds_max[param_name].clear()

    @Slot()
    def start_fitting_clicked(self):
        """Handle Start Fitting button click."""
        if self.main_window.raw_csv_path is None:
            QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        # Prepare fitting parameters
        model_type = self.model_combo.currentText().lower()

        # Collect initial parameters and bounds only if manual mode is enabled
        init_params = {}
        user_bounds = {}
        if hasattr(self, "use_manual_params") and self.use_manual_params.isChecked():
            for param_name, line_edit in self.param_inputs.items():
                # Collect parameter value if provided
                text = line_edit.text().strip()
                if text:
                    try:
                        value = float(text)
                        init_params[param_name] = value
                    except ValueError:
                        QMessageBox.warning(
                            self, 
                            "Invalid Parameter", 
                            f"Invalid value for {param_name}: {text}"
                        )
                        return
                
                # Collect custom bounds if provided
                if param_name in self.param_bounds_min:
                    min_text = self.param_bounds_min[param_name].text().strip()
                    max_text = self.param_bounds_max[param_name].text().strip()
                    
                    if min_text or max_text:
                        try:
                            # Get defaults as fallback
                            default_min = self.param_defaults[param_name]['min']
                            default_max = self.param_defaults[param_name]['max']
                            
                            min_val = float(min_text) if min_text else default_min
                            max_val = float(max_text) if max_text else default_max
                            
                            if min_val >= max_val:
                                QMessageBox.warning(
                                    self,
                                    "Invalid Bounds",
                                    f"For {param_name}: min ({min_val}) must be less than max ({max_val})"
                                )
                                return
                            
                            user_bounds[param_name] = (min_val, max_val)
                            
                            # Validate parameter value against custom bounds
                            if param_name in init_params:
                                if not (min_val <= init_params[param_name] <= max_val):
                                    QMessageBox.warning(
                                        self,
                                        "Invalid Parameter",
                                        f"{param_name} value {init_params[param_name]} is out of custom bounds [{min_val}, {max_val}]"
                                    )
                                    return
                        except ValueError as e:
                            QMessageBox.warning(
                                self,
                                "Invalid Bounds",
                                f"Invalid bounds for {param_name}: {e}"
                            )
                            return

        # Empty dict means use model's automatic parameter estimation
        fitting_params = {
            "model_params": init_params,
            "model_bounds": user_bounds,
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
        cell_id_text = self.cell_id_input.text().strip()
        if not cell_id_text:
            QMessageBox.warning(self, "No Cell ID", "Please enter a cell ID.")
            return

        try:
            cell_id = int(cell_id_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid Cell ID", "Cell ID must be a number.")
            return

        self.visualize_cell(cell_id)

    @Slot()
    def shuffle_clicked(self):
        """Handle Shuffle button click to select random cell."""
        if self.main_window.raw_data is None:
            return

        cell_ids = self.main_window.raw_data.columns
        random_cell = np.random.choice(cell_ids)
        self.cell_id_input.setText(str(random_cell))
        self.visualize_cell(random_cell)

    def visualize_cell(self, cell_id: int):
        """Visualize a specific cell in the QC plot."""
        if self.main_window.raw_data is None:
            return

        # Check if cell exists in the columns
        if cell_id not in self.main_window.raw_data.columns:
            QMessageBox.warning(
                self, "Cell Not Found", f"Cell ID '{cell_id}' not found in data."
            )
            return

        # Get cell data from wide format DataFrame
        time_data = self.main_window.raw_data.index
        intensity_data = self.main_window.raw_data[cell_id]

        # Clear and update QC plot
        self.qc_ax.clear()

        # Plot the raw data first (underneath)
        self.qc_ax.scatter(
            time_data,
            intensity_data,
            color="blue",
            alpha=0.6,
            s=20,
            label=f"Cell {cell_id} (data)",
            zorder=1,  # Draw underneath
        )

        # If we have fitting results, overlay the fitted curve
        if self.main_window.fitted_results is not None and not self.main_window.fitted_results.empty:
            # Try to find this cell in the fitting results
            cell_fit = self.main_window.fitted_results[
                self.main_window.fitted_results["cell_id"] == cell_id
            ]
            
            # Check if the fit was successful before plotting
            if not cell_fit.empty and 'success' in cell_fit.columns and cell_fit.iloc[0]["success"]:
                # Get the model type to reconstruct the fitted curve
                model_type = cell_fit.iloc[0].get("model_type", "").lower()
                
                # Import model functions
                from pyama_qt.analysis.models import get_model, get_types
                
                # Get the appropriate model
                try:
                    model = get_model(model_type)
                    types = get_types(model_type)
                except ValueError:
                    model = None
                
                if model is not None:
                    # Get the fitted parameters from the dataframe
                    param_names = list(model.DEFAULTS.keys())
                    params_dict = {}
                    
                    for param_name in param_names:
                        if param_name in cell_fit.columns and pd.notna(cell_fit.iloc[0][param_name]):
                            params_dict[param_name] = float(cell_fit.iloc[0][param_name])
                    
                    # Only plot if we have all required parameters
                    if len(params_dict) == len(param_names):
                        # Generate smooth curve for visualization
                        t_smooth = np.linspace(
                            time_data.min(),
                            time_data.max(),
                            200
                        )
                        y_fit = model.eval(t_smooth, params_dict)
                        
                        # Plot the fitted curve on top
                        r_squared = cell_fit.iloc[0].get('r_squared', 0)
                        self.qc_ax.plot(
                            t_smooth,
                            y_fit,
                            color="red",
                            linewidth=2,
                            label=f"Fit (R²={r_squared:.3f})",
                            zorder=2,  # Draw on top
                        )

        self.qc_ax.set_xlabel("Time")
        self.qc_ax.set_ylabel("Intensity")
        self.qc_ax.set_title(f"Quality Control - Cell {cell_id}")
        self.qc_ax.grid(True, alpha=0.3)
        self.qc_ax.legend()

        self.qc_canvas.draw()

    def set_cell_id(self, cell_id: int | str):
        """Set the cell ID in the input field."""
        self.cell_id_input.setText(str(cell_id))

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
        current_cell_text = self.cell_id_input.text().strip()
        if current_cell_text:
            try:
                current_cell = int(current_cell_text)
                self.visualize_cell(current_cell)
            except ValueError:
                pass
