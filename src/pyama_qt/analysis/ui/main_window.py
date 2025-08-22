"""
Main window for the Analysis application with three-panel layout.
"""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QStatusBar,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, Slot, QThread
from pathlib import Path
from typing import Dict, Any
import pandas as pd

from ..services.workflow import AnalysisWorkflowCoordinator
from pyama_qt.utils.logging_config import get_logger
from .widgets import DataPanel, FittingPanel, ResultsPanel


class MainWindow(QMainWindow):
    """Main window with three-panel layout for batch fitting analysis."""

    # Signals
    fitting_requested = Signal(Path, dict)  # data_path, params

    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        
        # Centralized data storage
        self.raw_data = None  # pandas DataFrame with raw CSV data
        self.raw_csv_path = None  # Path to raw CSV file
        self.fitted_results = None  # pandas DataFrame with fitted results
        self.fitted_csv_path = None  # Path to fitted CSV file

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

        # Create three panels with MainWindow reference
        self.data_panel = DataPanel(main_window=self)
        self.fitting_panel = FittingPanel(self)
        self.results_panel = ResultsPanel(main_window=self)

        # Add panels to splitter
        self.splitter.addWidget(self.data_panel)
        self.splitter.addWidget(self.fitting_panel)
        self.splitter.addWidget(self.results_panel)

        # Set initial splitter sizes (equal width)
        self.splitter.setSizes([450, 400, 550])

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready to load data")

        # Connect signals between panels
        self.connect_panel_signals()

    def connect_panel_signals(self):
        """Connect signals between the different panels."""
        # Data panel signals
        self.data_panel.data_loaded.connect(self.on_data_loaded)
        self.data_panel.fitted_results_found.connect(self.on_fitted_results_found)

        # Fitting panel signals
        self.fitting_panel.fitting_requested.connect(self.fitting_requested)

    @Slot(Path, pd.DataFrame)
    def on_data_loaded(self, csv_path: Path, data: pd.DataFrame):
        """Handle data loaded from data panel."""
        # Store data centrally
        self.raw_data = data
        self.raw_csv_path = csv_path
        
        # Update fitting panel with data
        self.fitting_panel.set_data(csv_path, data)

        # Update status bar
        n_cells = len(data["cell_id"].unique())
        self.status_bar.showMessage(f"Loaded {n_cells} cells from {csv_path.name}")

    @Slot(pd.DataFrame)
    def on_fitted_results_found(self, fitted_df: pd.DataFrame):
        """Handle fitted results found by data panel."""
        # Store fitted results centrally
        self.fitted_results = fitted_df
        if self.raw_csv_path:
            self.fitted_csv_path = self.raw_csv_path.parent / f"{self.raw_csv_path.stem}_fitted.csv"
        
        # Update panels
        self.results_panel.update_fitting_results(fitted_df)
        self.fitting_panel.update_fitting_results(fitted_df)
        self.logger.info(f"Auto-loaded {len(fitted_df)} fitted results")
        
        # Update status bar to show both data and results
        current_msg = self.status_bar.currentMessage()
        self.status_bar.showMessage(f"{current_msg} + {len(fitted_df)} fitted results")

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
        if self.workflow_thread is not None:
            QMessageBox.warning(self, "Busy", "A fitting process is already running.")
            return

        self.logger.info(f"Starting fitting workflow for {data_path}")

        self.workflow_thread = QThread()
        # Pass parameters to the worker's constructor
        self.workflow_coordinator = AnalysisWorkflowCoordinator(
            data_folder=data_path,
            model_type=params["model_type"],
            fitting_params=params["fitting_params"],
            batch_size=params.get("batch_size", 10),
            n_workers=params.get("n_workers", 4),
            data_format=params.get("data_format", "simple"),
        )
        self.workflow_coordinator.moveToThread(self.workflow_thread)

        self.collected_results = []

        # Connect signals from worker
        self.workflow_coordinator.progress_updated.connect(self.on_progress_updated)
        self.workflow_coordinator.status_updated.connect(self.on_status_updated)
        self.workflow_coordinator.error_occurred.connect(self.on_error_occurred)
        self.workflow_coordinator.batch_completed.connect(self.on_batch_completed)
        self.workflow_coordinator.workflow_completed.connect(self.on_workflow_completed)
        
        # Connect thread lifecycle
        self.workflow_thread.started.connect(self.workflow_coordinator.run) # Correct connection
        self.workflow_coordinator.workflow_completed.connect(self.workflow_thread.quit)
        self.workflow_thread.finished.connect(self.on_workflow_finished)

        # Disable button and start
        self.fitting_panel.set_fitting_active(True)
        self.workflow_thread.start()
        self.status_bar.showMessage("Starting batch fitting...")

    @Slot(bool, str)
    def on_workflow_completed(self, success: bool, data_path_str: str):
        """Handle workflow completion signal from the worker."""
        if success and data_path_str:
            data_path = Path(data_path_str)
            self.collect_and_emit_results(data_path)

    @Slot(int)
    def on_progress_updated(self, progress: int):
        """Handle progress updates from the worker."""
        # The visual progress is now handled by the indeterminate progress bar.
        # We can still use the text status updates.
        pass

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
    def on_batch_completed(self, dataset_name: str, results: Dict):
        """Handle batch completion for a dataset."""
        self.logger.info(f"Dataset {dataset_name} completed")
        if "results" in results:
            self.collected_results.extend(results["results"])

    def on_workflow_finished(self):
        """Handle the QThread.finished signal."""
        self.logger.info("Workflow thread finished")
        self.fitting_panel.set_fitting_active(False)

        # Clean up thread and worker
        if self.workflow_thread:
            self.workflow_thread.deleteLater()
            self.workflow_thread = None
        if self.workflow_coordinator:
            self.workflow_coordinator.deleteLater()
            self.workflow_coordinator = None

    def collect_and_emit_results(self, data_path: Path):
        """Collect and emit final results."""
        try:
            if data_path.is_file():
                fitted_path = data_path.parent / f"{data_path.stem}_fitted.csv"
            else:
                fitted_files = list(data_path.glob("*_fitted.csv"))
                if not fitted_files:
                    self.logger.warning("No fitted results found")
                    return
                fitted_path = fitted_files[0]

            if fitted_path.exists():
                results_df = pd.read_csv(fitted_path)
                # Store fitted results centrally
                self.fitted_results = results_df
                self.fitted_csv_path = fitted_path
                
                # Update panels
                self.results_panel.update_fitting_results(results_df)
                self.fitting_panel.update_fitting_results(results_df)
                self.logger.info(f"Loaded {len(results_df)} fitting results")
                self.status_bar.showMessage(f"Fitting complete: {len(results_df)} cells processed")
            else:
                self.logger.warning(f"Results file not found: {fitted_path}")

        except Exception as e:
            self.logger.error(f"Error loading results: {e}")
            self.show_error(f"Failed to load results: {str(e)}")