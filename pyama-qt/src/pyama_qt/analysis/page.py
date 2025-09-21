"""
Main window for the Analysis application with three-panel layout.
"""

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QStatusBar,
    QMessageBox,
)
from PySide6.QtCore import Signal, Slot, QThread, QObject
from pathlib import Path
from typing import Dict, Any
import pandas as pd

import logging

from .widgets import DataPanel, FittingPanel, ResultsPanel
from pyama_core.io.analysis_csv import discover_csv_files, load_analysis_csv
from pyama_core.analysis.fitting import fit_trace_data

logger = logging.getLogger(__name__)


class AnalysisWorker(QObject):
    """Worker class for trace fitting analysis in a background thread."""

    # Signals for communication with the main thread
    progress_updated = Signal(str)  # Message about current progress
    file_processed = Signal(
        str, object
    )  # Emitted when a file is processed (file name, results dataframe)
    finished = Signal()  # Emitted when all processing is complete
    error_occurred = Signal(str)  # Emitted when an error occurs

    def __init__(
        self, data_folder: Path, model_type: str, fitting_params: dict | None = None
    ):
        """
        Initialize the worker.

        Args:
            data_folder: Path to folder containing CSV files
            model_type: Type of model to fit ('trivial', 'maturation', etc.)
            fitting_params: Optional fitting parameters including initial values
        """
        super().__init__()
        self.data_folder = data_folder
        self.model_type = model_type
        self.fitting_params = fitting_params or {}
        self._is_cancelled = False

    def process_data(self):
        """Process trace data in the background thread."""
        try:
            # Discover files
            self.progress_updated.emit("Discovering CSV files...")
            trace_files = discover_csv_files(self.data_folder)

            if not trace_files:
                self.error_occurred.emit(f"No CSV files found in {self.data_folder}")
                return

            self.progress_updated.emit(f"Found {len(trace_files)} file(s)")

            # Process each file
            for i, trace_path in enumerate(trace_files):
                if self._is_cancelled:
                    self.progress_updated.emit("Processing cancelled")
                    break

                self.progress_updated.emit(
                    f"Processing {trace_path.name} ({i + 1}/{len(trace_files)})..."
                )

                try:
                    # Load data
                    df = load_analysis_csv(trace_path)
                    n_cells = df.shape[1]
                    results = []

                    logger.info(f"Fitting {n_cells} cells from {trace_path.name}")

                    def progress_callback(cell_id):
                        if cell_id % 30 == 0 or cell_id == n_cells - 1:
                            progress_percent = int((cell_id + 1) / n_cells * 100)
                            progress_msg = (
                                f"Fitting cell {cell_id + 1}/{n_cells} ({progress_percent}%) "
                                f"in {trace_path.name}..."
                            )
                            # Emit signal for UI status bar
                            self.progress_updated.emit(progress_msg)
                            # Log to file/console
                            logger.info(progress_msg)

                    # Fit each cell
                    for cell_idx in range(n_cells):
                        if self._is_cancelled:
                            break

                        try:
                            fit_result = fit_trace_data(
                                df,
                                self.model_type,
                                cell_idx,
                                progress_callback=progress_callback,
                                user_params=self.fitting_params.get("model_params"),
                                user_bounds=self.fitting_params.get("model_bounds"),
                            )

                            # Prepare result record
                            record = {
                                "cell_id": cell_idx,
                                "model_type": self.model_type,
                                "success": fit_result.success,
                                "r_squared": fit_result.r_squared,
                            }
                            record.update(fit_result.fitted_params)
                            results.append(record)

                        except Exception as e:
                            logger.error(f"Error fitting cell {cell_idx}: {e}")
                            # Continue with other cells
                            continue

                    # Save results
                    if results:
                        results_df = pd.DataFrame(results)
                        output_path = (
                            trace_path.parent / f"{trace_path.stem}_fitted.csv"
                        )
                        results_df.to_csv(output_path, index=False)
                        logger.info(f"Saved {len(results)} results to {output_path}")

                        # Notify that this file is processed
                        self.file_processed.emit(trace_path.name, results_df)

                except Exception as e:
                    logger.error(f"Error processing {trace_path.name}: {e}")
                    self.error_occurred.emit(f"Error processing {trace_path.name}: {e}")
                    # Continue with other files
                    continue

            self.progress_updated.emit("Completed processing all files")

        except Exception as e:
            logger.exception(f"Critical error: {e}")
            self.error_occurred.emit(f"Critical error: {e}")
        finally:
            self.finished.emit()

    def cancel(self):
        """Cancel the processing."""
        self._is_cancelled = True
        logger.info("Processing cancellation requested")


class AnalysisPage(QWidget):
    """Embeddable analysis page (QWidget) containing the analysis UI and logic."""

    # Signals (kept within the page)
    fitting_requested = Signal(Path, dict)  # data_path, params

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # Centralized data storage
        self.raw_data = None  # pandas DataFrame with raw CSV data
        self.raw_csv_path = None  # Path to raw CSV file
        self.fitted_results = None  # pandas DataFrame with fitted results
        self.fitted_csv_path = None  # Path to fitted CSV file

        # Workflow thread management
        self.workflow_thread = None
        self.workflow_worker = None
        self.collected_results = []

        self.setup_ui()

        # Connect fitting signal
        self.fitting_requested.connect(self.start_fitting)

        logger.info("PyAMA Analysis Page loaded")

    def setup_ui(self):
        """Set up the three-panel UI layout inside this widget."""
        main_layout = QHBoxLayout(self)

        # Create three panels with page reference
        self.data_panel = DataPanel(self)
        self.fitting_panel = FittingPanel(self)
        self.results_panel = ResultsPanel(self)

        # Add panels to layout with equal stretch factors
        main_layout.addWidget(self.data_panel, 1)  # Stretch factor 1
        main_layout.addWidget(self.fitting_panel, 1)  # Stretch factor 1
        main_layout.addWidget(self.results_panel, 1)  # Stretch factor 1

        # Create an embedded status bar-like widget
        self.status_bar = QStatusBar(self)
        self.status_bar.showMessage("Ready to load data")
        main_layout.addWidget(self.status_bar)

        # Connect signals between panels
        self.connect_panel_signals()

    def connect_panel_signals(self):
        """Connect signals between the different panels."""
        # Data panel signals
        self.data_panel.data_loaded.connect(self.on_data_loaded)
        self.data_panel.fitted_results_found.connect(self.on_fitted_results_found)

        # Fitting panel signals
        self.fitting_panel.fitting_requested.connect(self.fitting_requested)

    @Slot(Path, object)  # object for pd.DataFrame
    def on_data_loaded(self, csv_path: Path, data: pd.DataFrame):
        """Handle data loaded from data panel."""
        # Store data centrally
        self.raw_data = data
        self.raw_csv_path = csv_path

        # Update fitting panel with data
        self.fitting_panel.set_data(csv_path, data)

        # Update data panel plot now that data is stored
        self.data_panel.plot_all_sequences()

        # Update status bar
        n_cells = len(data.columns)
        self.status_bar.showMessage(f"Loaded {n_cells} cells from {csv_path.name}")

    @Slot(object)  # object for pd.DataFrame
    def on_fitted_results_found(self, fitted_df: pd.DataFrame):
        """Handle fitted results found by data panel."""
        # Store fitted results centrally
        self.fitted_results = fitted_df
        if self.raw_csv_path:
            self.fitted_csv_path = (
                self.raw_csv_path.parent / f"{self.raw_csv_path.stem}_fitted.csv"
            )

        # Update panels
        self.results_panel.update_fitting_results(fitted_df)
        self.fitting_panel.update_fitting_results(fitted_df)
        logger.info(f"Auto-loaded {len(fitted_df)} fitted results")

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

        logger.info(f"Starting fitting workflow for {data_path}")

        self.workflow_thread = QThread()
        # Pass parameters to the worker's constructor
        self.workflow_worker = AnalysisWorker(
            data_folder=data_path,
            model_type=params["model_type"],
            fitting_params=params.get("fitting_params", {}),
        )
        self.workflow_worker.moveToThread(self.workflow_thread)

        self.collected_results = []

        # Connect signals from worker
        self.workflow_worker.progress_updated.connect(self.on_status_updated)
        self.workflow_worker.error_occurred.connect(self.on_error_occurred)
        self.workflow_worker.file_processed.connect(self.on_file_processed)
        self.workflow_worker.finished.connect(self.on_workflow_completed)

        # Connect thread lifecycle
        self.workflow_thread.started.connect(self.workflow_worker.process_data)
        self.workflow_worker.finished.connect(self.workflow_thread.quit)
        self.workflow_thread.finished.connect(self.on_workflow_finished)

        # Disable button and start
        self.fitting_panel.set_fitting_active(True)
        self.workflow_thread.start()
        self.status_bar.showMessage("Starting batch fitting...")

    @Slot(str, object)  # Use object instead of pd.DataFrame for PySide6 compatibility
    def on_file_processed(self, filename: str, results_df: pd.DataFrame):
        """Handle file processed signal from the worker."""
        logger.info(f"File processed: {filename}")
        self.status_bar.showMessage(f"Processed: {filename}")

        # Update fitted results immediately
        self.fitted_results = results_df
        self.fitting_panel.update_fitting_results(results_df)
        self.results_panel.update_fitting_results(results_df)

    @Slot()
    def on_workflow_completed(self):
        """Handle workflow completion signal from the worker."""
        if self.raw_csv_path:
            data_path = self.raw_csv_path.parent
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
        logger.error(error)

    def on_workflow_finished(self):
        """Handle the QThread.finished signal."""
        logger.info("Workflow thread finished")
        self.fitting_panel.set_fitting_active(False)

        # Clean up thread and worker
        if self.workflow_thread:
            self.workflow_thread.deleteLater()
            self.workflow_thread = None
        if self.workflow_worker:
            self.workflow_worker.deleteLater()
            self.workflow_worker = None

    def collect_and_emit_results(self, data_path: Path):
        """Collect and emit final results."""
        try:
            if data_path.is_file():
                fitted_path = data_path.parent / f"{data_path.stem}_fitted.csv"
            else:
                fitted_files = list(data_path.glob("*_fitted.csv"))
                if not fitted_files:
                    logger.warning("No fitted results found")
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
                logger.info(f"Loaded {len(results_df)} fitting results")
                self.status_bar.showMessage(
                    f"Fitting complete: {len(results_df)} cells processed"
                )
            else:
                logger.warning(f"Results file not found: {fitted_path}")

        except Exception as e:
            logger.error(f"Error loading results: {e}")
            self.show_error(f"Failed to load results: {str(e)}")
