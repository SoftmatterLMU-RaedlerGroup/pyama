"""
Main window for the Analysis application with three-panel layout.
"""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QDoubleSpinBox,
    QLineEdit,
    QComboBox,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QLabel,
)
from PySide6.QtCore import Qt, Signal, Slot, QThread
from pathlib import Path
from typing import Dict, Any
import numpy as np
import pandas as pd

# Matplotlib imports
import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from pyama_qt.core.csv_loader import load_simple_csv
from ..services.workflow import AnalysisWorkflowCoordinator
from pyama_qt.core.logging_config import get_logger


class MplCanvas(FigureCanvas):
    """Matplotlib canvas widget for embedding plots in Qt."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)


class MainWindow(QMainWindow):
    """Main window with three-panel layout for batch fitting analysis."""

    # Signals
    fitting_requested = Signal(Path, dict)  # data_path, params

    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        self.current_data = None
        self.current_csv_path = None
        self.fitting_results = None

        # Workflow thread management
        self.workflow_thread = None
        self.workflow_coordinator = None
        self.collected_results = []

        self.setup_ui()
        self.setWindowTitle("PyAMA-Qt Cell Kinetics Batch Fitting")
        self.resize(1400, 800)

        # Connect fitting signal
        self.fitting_requested.connect(self.start_fitting)

    def setup_ui(self):
        """Set up the three-panel UI layout."""
        # Create central widget and main splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Create horizontal splitter for three panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        # Create three panels
        self.left_panel = self.create_left_panel()
        self.middle_panel = self.create_middle_panel()
        self.right_panel = self.create_right_panel()

        # Add panels to splitter
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.middle_panel)
        self.splitter.addWidget(self.right_panel)

        # Set initial splitter sizes (equal width)
        self.splitter.setSizes([450, 400, 550])

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready to load data")

    def create_left_panel(self) -> QWidget:
        """Create left panel with Load CSV button and data visualization."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Load CSV button
        self.load_csv_btn = QPushButton("Load CSV")
        self.load_csv_btn.clicked.connect(self.load_csv_clicked)
        layout.addWidget(self.load_csv_btn)

        # All sequences plot
        self.data_canvas = MplCanvas(self, width=5, height=8)
        layout.addWidget(self.data_canvas)

        # Initialize empty plot
        self.data_ax = self.data_canvas.fig.add_subplot(111)
        self.data_ax.set_xlabel("Time")
        self.data_ax.set_ylabel("Intensity")
        self.data_ax.set_title("All Sequences")
        self.data_ax.grid(True, alpha=0.3)
        self.data_canvas.draw()

        layout.addStretch()
        return panel

    def create_middle_panel(self) -> QWidget:
        """Create middle panel with fitting controls."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Fitting Parameters Group
        params_group = QGroupBox("Fitting Parameters")
        params_layout = QFormLayout()

        # Model selection
        self.model_combo = QComboBox()
        self.model_combo.addItems(["Trivial", "Two-Stage", "Maturation"])
        params_layout.addRow("Model:", self.model_combo)

        # Parameter spinboxes (will be populated based on model)
        self.param_spinboxes = {}

        # Common parameters (removed n_starts and noise_level as we use single-start optimization)

        # Add some model-specific parameters (simplified for now)
        self.t0_spinbox = QDoubleSpinBox()
        self.t0_spinbox.setRange(0.0, 100.0)
        self.t0_spinbox.setSingleStep(0.1)
        self.t0_spinbox.setValue(2.0)
        params_layout.addRow("t0:", self.t0_spinbox)

        self.amplitude_spinbox = QDoubleSpinBox()
        self.amplitude_spinbox.setRange(0.0, 1e6)
        self.amplitude_spinbox.setSingleStep(100)
        self.amplitude_spinbox.setValue(1000.0)
        params_layout.addRow("Amplitude:", self.amplitude_spinbox)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # Start Batch Fitting button
        self.start_fitting_btn = QPushButton("Start Batch Fitting")
        self.start_fitting_btn.clicked.connect(self.start_fitting_clicked)
        self.start_fitting_btn.setEnabled(False)
        layout.addWidget(self.start_fitting_btn)

        # Quality Control Section
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
        self.visualize_btn.clicked.connect(self.visualize_cell_clicked)
        self.visualize_btn.setEnabled(False)
        btn_layout.addWidget(self.visualize_btn)

        self.shuffle_btn = QPushButton("Shuffle")
        self.shuffle_btn.clicked.connect(self.shuffle_clicked)
        self.shuffle_btn.setEnabled(False)
        btn_layout.addWidget(self.shuffle_btn)

        qc_layout.addLayout(btn_layout)
        qc_group.setLayout(qc_layout)
        layout.addWidget(qc_group)

        layout.addStretch()
        return panel

    def create_right_panel(self) -> QWidget:
        """Create right panel with quality plots."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Fitting Quality Plot
        quality_label = QLabel("Fitting Quality")
        quality_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(quality_label)

        self.quality_canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self.quality_canvas)

        # Initialize quality plot
        self.quality_ax = self.quality_canvas.fig.add_subplot(111)
        self.quality_ax.set_xlabel("Cell Index")
        self.quality_ax.set_ylabel("R² Score")
        self.quality_ax.set_title("Fitting Quality")
        self.quality_ax.grid(True, alpha=0.3)
        self.quality_canvas.draw()

        # Parameter selection dropdown
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("Parameter:"))
        self.param_combo = QComboBox()
        self.param_combo.addItems(["t0", "amplitude", "rate", "offset"])
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
        return panel

    @Slot()
    def load_csv_clicked(self):
        """Handle Load CSV button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)"
        )

        if file_path:
            self.load_csv_file(Path(file_path))

    def load_csv_file(self, csv_path: Path):
        """Load and visualize CSV data."""
        try:
            self.status_bar.showMessage(f"Loading {csv_path.name}...")

            # Load data in long format with baseline correction (shift to start at zero)
            self.current_data = load_simple_csv(csv_path, baseline_correct=True)
            self.current_csv_path = csv_path

            # Get unique cells
            cell_ids = self.current_data["cell_id"].unique()
            n_cells = len(cell_ids)

            self.logger.info(f"Loaded {n_cells} cells from {csv_path.name}")

            # Update data plot
            self.plot_all_sequences()

            # Enable controls
            self.start_fitting_btn.setEnabled(True)
            self.visualize_btn.setEnabled(True)
            self.shuffle_btn.setEnabled(True)

            self.status_bar.showMessage(f"Loaded {n_cells} cells from {csv_path.name}")

        except Exception as e:
            self.logger.error(f"Error loading CSV: {e}")
            QMessageBox.critical(self, "Load Error", f"Failed to load CSV:\n{str(e)}")

    def plot_all_sequences(self):
        """Plot all sequences in gray with mean in red."""
        if self.current_data is None:
            return

        # Clear previous plot
        self.data_ax.clear()

        # Get unique cells
        cell_ids = self.current_data["cell_id"].unique()

        # Collect all traces for mean calculation
        all_traces = []

        # Plot each cell in gray
        for cell_id in cell_ids[:100]:  # Limit to first 100 for performance
            cell_data = self.current_data[self.current_data["cell_id"] == cell_id]
            time = cell_data["time"].values
            intensity = cell_data["intensity_total"].values

            self.data_ax.plot(time, intensity, color="gray", alpha=0.2, linewidth=0.5)
            all_traces.append(intensity)

        # Calculate and plot mean in red
        if all_traces:
            # Ensure all traces have same length (they should from the CSV format)
            min_len = min(len(trace) for trace in all_traces)
            all_traces_array = np.array([trace[:min_len] for trace in all_traces])
            mean_trace = np.mean(all_traces_array, axis=0)

            # Get time values for mean
            sample_cell = self.current_data[self.current_data["cell_id"] == cell_ids[0]]
            time_values = sample_cell["time"].values[:min_len]

            self.data_ax.plot(
                time_values,
                mean_trace,
                color="red",
                linewidth=2,
                label="Mean",
                alpha=0.8,
            )

        self.data_ax.set_xlabel("Time")
        self.data_ax.set_ylabel("Intensity")
        self.data_ax.set_title(f"All Sequences ({len(cell_ids)} cells)")
        self.data_ax.grid(True, alpha=0.3)
        self.data_ax.legend()

        self.data_canvas.draw()

    @Slot()
    def start_fitting_clicked(self):
        """Handle Start Batch Fitting button click."""
        if self.current_csv_path is None:
            QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        # Prepare fitting parameters
        model_type = self.model_combo.currentText().lower()
        if model_type == "two-stage":
            model_type = "twostage"

        fitting_params = {
            "model_params": {},
        }

        # Emit signal to start fitting
        self.fitting_requested.emit(
            self.current_csv_path,
            {
                "model_type": model_type,
                "fitting_params": fitting_params,
                "data_format": "simple",
            },
        )

        self.status_bar.showMessage("Starting batch fitting...")

    @Slot()
    def visualize_cell_clicked(self):
        """Visualize specific cell fit."""
        cell_id = self.cell_id_input.text().strip()
        if not cell_id:
            QMessageBox.warning(self, "No Cell ID", "Please enter a cell ID.")
            return

        if self.current_data is None:
            return

        # Check if cell exists
        if cell_id not in self.current_data["cell_id"].values:
            QMessageBox.warning(
                self, "Cell Not Found", f"Cell ID '{cell_id}' not found in data."
            )
            return

        # Get cell data
        cell_data = self.current_data[self.current_data["cell_id"] == cell_id]

        # Update data plot to highlight this cell
        self.data_ax.clear()

        # Plot all in gray (faded)
        for other_id in self.current_data["cell_id"].unique()[:50]:
            if other_id != cell_id:
                other_data = self.current_data[self.current_data["cell_id"] == other_id]
                self.data_ax.plot(
                    other_data["time"].values,
                    other_data["intensity_total"].values,
                    color="gray",
                    alpha=0.1,
                    linewidth=0.5,
                )

        # Plot selected cell in blue
        self.data_ax.plot(
            cell_data["time"].values,
            cell_data["intensity_total"].values,
            color="blue",
            linewidth=2,
            label=f"Cell {cell_id}",
        )

        self.data_ax.set_xlabel("Time")
        self.data_ax.set_ylabel("Intensity")
        self.data_ax.set_title(f"Cell {cell_id} Highlighted")
        self.data_ax.grid(True, alpha=0.3)
        self.data_ax.legend()

        self.data_canvas.draw()

        self.status_bar.showMessage(f"Visualizing cell {cell_id}")

    @Slot()
    def shuffle_clicked(self):
        """Select random cell for visualization."""
        if self.current_data is None:
            return

        cell_ids = self.current_data["cell_id"].unique()
        random_cell = np.random.choice(cell_ids)

        self.cell_id_input.setText(str(random_cell))
        self.visualize_cell_clicked()

    @Slot(str)
    def update_param_histogram(self, param_name):
        """Update parameter histogram based on selection."""
        if self.fitting_results is None:
            return

        self.param_ax.clear()

        # Check if parameter exists in results
        if param_name in self.fitting_results.columns:
            values = self.fitting_results[param_name].dropna().values

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

    def update_fitting_results(self, results_df: pd.DataFrame):
        """Update plots with fitting results."""
        self.fitting_results = results_df

        # Update quality plot
        self.quality_ax.clear()

        if "r_squared" in results_df.columns:
            r_squared_values = results_df["r_squared"].values
            self.quality_ax.scatter(
                range(len(r_squared_values)), r_squared_values, alpha=0.6, s=10
            )
            self.quality_ax.axhline(
                y=0.9, color="r", linestyle="--", alpha=0.5, label="R²=0.9"
            )

        self.quality_ax.set_xlabel("Cell Index")
        self.quality_ax.set_ylabel("R² Score")
        self.quality_ax.set_title("Fitting Quality")
        self.quality_ax.grid(True, alpha=0.3)
        self.quality_ax.legend()
        self.quality_canvas.draw()

        # Update parameter histogram
        self.update_param_histogram(self.param_combo.currentText())

        self.status_bar.showMessage(
            f"Fitting complete: {len(results_df)} cells processed"
        )

    @Slot(int)
    def update_progress(self, progress: int):
        """Update progress display."""
        self.status_bar.showMessage(f"Progress: {progress}%")

    @Slot(str)
    def show_error(self, error_msg: str):
        """Show error message."""
        QMessageBox.critical(self, "Error", error_msg)

    @Slot(Path, dict)
    def start_fitting(self, data_path: Path, params: Dict[str, Any]):
        """Start the fitting workflow."""

        self.logger.info(f"Starting fitting workflow for {data_path}")

        # Create workflow thread
        self.workflow_thread = QThread()

        # Create workflow coordinator
        self.workflow_coordinator = AnalysisWorkflowCoordinator()
        self.workflow_coordinator.moveToThread(self.workflow_thread)

        # Clear previous results
        self.collected_results = []

        # Connect signals
        self.workflow_coordinator.progress_updated.connect(self.on_progress_updated)
        self.workflow_coordinator.status_updated.connect(self.on_status_updated)
        self.workflow_coordinator.error_occurred.connect(self.on_error_occurred)
        self.workflow_coordinator.fov_completed.connect(self.on_fov_completed)

        # Connect thread lifecycle
        self.workflow_thread.started.connect(
            lambda: self.run_workflow(data_path, params)
        )
        self.workflow_thread.finished.connect(self.on_workflow_finished)

        # Start thread
        self.workflow_thread.start()

    def run_workflow(self, data_path: Path, params: Dict):
        """Run the workflow in the thread."""

        try:
            success = self.workflow_coordinator.run_fitting_workflow(
                data_folder=data_path if data_path.is_dir() else data_path.parent,
                model_type=params["model_type"],
                fitting_params=params["fitting_params"],
                batch_size=params.get("batch_size", 10),
                n_workers=params.get("n_workers", 4),
                data_format=params.get("data_format", "simple"),
            )

            if success:
                self.logger.info("Workflow completed successfully")
                self.collect_and_emit_results(data_path)
            else:
                self.logger.warning("Workflow completed with errors")

        except Exception as e:
            self.logger.exception(f"Error in workflow: {e}")
            self.show_error(str(e))
        finally:
            if self.workflow_thread:
                self.workflow_thread.quit()

    @Slot(int)
    def on_progress_updated(self, progress: int):
        """Handle progress updates."""
        self.update_progress(progress)

    @Slot(str)
    def on_status_updated(self, message: str):
        """Handle status updates."""
        self.status_bar.showMessage(message)

    @Slot(str)
    def on_error_occurred(self, error: str):
        """Handle errors."""
        self.show_error(error)
        self.logger.error(error)

    @Slot(str, dict)
    def on_fov_completed(self, fov_name: str, results: Dict):
        """Handle FOV completion."""

        self.logger.info(f"FOV {fov_name} completed")

        # Collect results
        if "results" in results:
            self.collected_results.extend(results["results"])

    def on_workflow_finished(self):
        """Handle workflow completion."""
        self.logger.info("Workflow thread finished")

        # Clean up thread
        if self.workflow_thread:
            self.workflow_thread.deleteLater()
            self.workflow_thread = None

        self.workflow_coordinator = None

    def collect_and_emit_results(self, data_path: Path):
        """Collect and emit final results."""
        try:
            # Look for fitted CSV file
            if data_path.is_file():
                fitted_path = data_path.parent / f"{data_path.stem}_fitted.csv"
            else:
                # Find first fitted file in directory
                fitted_files = list(data_path.glob("*_fitted.csv"))
                if fitted_files:
                    fitted_path = fitted_files[0]
                else:
                    self.logger.warning("No fitted results found")
                    return

            if fitted_path.exists():
                results_df = pd.read_csv(fitted_path)
                self.update_fitting_results(results_df)
                self.logger.info(f"Loaded {len(results_df)} fitting results")
            else:
                self.logger.warning(f"Results file not found: {fitted_path}")

        except Exception as e:
            self.logger.error(f"Error loading results: {e}")
            self.show_error(f"Failed to load results: {str(e)}")
