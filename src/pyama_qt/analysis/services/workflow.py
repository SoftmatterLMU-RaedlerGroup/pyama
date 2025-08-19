"""
Workflow coordination for parallel trace fitting analysis.

Manages parallel execution of fitting across multiple FOVs.
"""

from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import logging
from logging.handlers import QueueListener
from typing import Dict, Any, Optional, List, Tuple

from .fitting_worker import process_fov_batch
from pyama_qt.utils.csv_loader import (
    create_fov_batches,
    discover_trace_files,
    discover_simple_csv_files,
    create_simple_csv_batches,
    process_simple_csv_batch,
)
from pyama_qt.utils.logging_config import get_logger


class AnalysisWorkflowCoordinator(QObject):
    """Coordinates parallel execution of trace fitting workflow."""

    progress_updated = Signal(int)  # Overall progress percentage (0-100)
    status_updated = Signal(str)  # Status message
    error_occurred = Signal(str)  # Error message
    batch_completed = Signal(str, dict)  # Batch identifier, results summary
    workflow_completed = Signal(bool, str)  # Success status, data path

    def __init__(self, data_folder: Path, model_type: str, fitting_params: Dict[str, Any], batch_size: int, n_workers: int, data_format: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_cancelled = False
        self.logger = get_logger(__name__)
        self.log_queue_listener = None
        # Store parameters
        self.data_folder = data_folder
        self.model_type = model_type
        self.fitting_params = fitting_params
        self.batch_size = batch_size
        self.n_workers = n_workers
        self.data_format = data_format

    @Slot()
    def run(self):
        """Public slot to start the workflow. Connect QThread.started to this."""
        self.run_fitting_workflow()

    def run_fitting_workflow(self) -> bool:
        """
        Run the trace fitting workflow with parallel processing.
        This method is blocking (within its own thread) but uses signals to update the UI.
        """
        self._is_cancelled = False
        overall_success = False

        log_queue = mp.Manager().Queue()
        handlers = logging.getLogger().handlers
        if not handlers:
            logging.basicConfig(level=logging.INFO)
            handlers = logging.getLogger().handlers

        self.log_queue_listener = QueueListener(log_queue, *handlers)
        self.log_queue_listener.start()

        try:
            self.status_updated.emit("Discovering trace files...")

            if self.data_format == "auto":
                if self.data_folder.is_file() and self.data_folder.suffix.lower() == ".csv":
                    self.data_format = "simple"
                elif any(d.name.startswith("fov_") for d in self.data_folder.iterdir() if d.is_dir()):
                    self.data_format = "fov"
                else:
                    self.data_format = "simple"
                self.logger.info(f"Auto-detected data format: {self.data_format}")

            if self.data_format == "fov":
                trace_files = discover_trace_files(self.data_folder)
                if not trace_files:
                    self.error_occurred.emit(f"No FOV trace CSV files found in {self.data_folder}")
                    return False
                self.status_updated.emit(f"Found {len(trace_files)} FOVs to process")
                fov_batches = create_fov_batches(trace_files, self.batch_size)
                process_func = process_fov_batch
            else:  # simple CSV format
                csv_files = discover_simple_csv_files(self.data_folder)
                if not csv_files:
                    self.error_occurred.emit(f"No CSV files found in {self.data_folder}")
                    return False
                self.status_updated.emit(f"Found {len(csv_files)} dataset(s) to process")
                fov_batches = create_simple_csv_batches(csv_files, self.batch_size)
                process_func = process_simple_csv_batch

            self.status_updated.emit(f"Starting parallel fitting with {self.n_workers} workers...")

            batch_stats = {
                "completed_batches": 0,
                "total_successful_fits": 0,
                "total_failed_fits": 0,
                "all_errors": [],
                "total_batches": len(fov_batches),
            }

            with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
                futures = {executor.submit(process_func, batch, self.model_type, self.fitting_params, log_queue): batch for batch in fov_batches}

                for future in as_completed(futures):
                    if self._is_cancelled:
                        break
                    
                    batch = futures[future]
                    try:
                        batch_result = future.result()
                        batch_stats["total_successful_fits"] += batch_result["successful_fits"]
                        batch_stats["total_failed_fits"] += batch_result["failed_fits"]
                        batch_stats["all_errors"].extend(batch_result["processing_errors"])

                        for dataset_name, dataset_result in batch_result["fov_results"].items():
                            self.batch_completed.emit(dataset_name, dataset_result)

                    except Exception as e:
                        error_msg = f"Error processing batch: {str(e)}"
                        self.logger.exception(error_msg)
                        self.error_occurred.emit(error_msg)
                        batch_stats["all_errors"].append(error_msg)

                    batch_stats["completed_batches"] += 1
                    progress = int((batch_stats["completed_batches"] / batch_stats["total_batches"]) * 100)
                    self.progress_updated.emit(progress)
                    self.status_updated.emit(f"Completed batch {batch_stats['completed_batches']}/{batch_stats['total_batches']}")

            total_cells = batch_stats["total_successful_fits"] + batch_stats["total_failed_fits"]
            success_rate = (batch_stats["total_successful_fits"] / total_cells * 100) if total_cells > 0 else 0
            final_message = f"Fitting completed: {batch_stats['total_successful_fits']}/{total_cells} cells ({success_rate:.1f}% success rate)"
            self.status_updated.emit(final_message)

            if batch_stats["all_errors"]:
                for error in batch_stats["all_errors"][:5]:
                    self.error_occurred.emit(f"Warning: {error}")

            overall_success = batch_stats["total_successful_fits"] > 0
            self.workflow_completed.emit(overall_success, str(self.data_folder))

        except Exception as e:
            error_msg = f"Critical error in fitting workflow: {str(e)}"
            self.logger.exception(error_msg)
            self.error_occurred.emit(error_msg)
            overall_success = False
        finally:
            if self.log_queue_listener:
                self.log_queue_listener.stop()
                self.log_queue_listener = None

        return overall_success

    def cancel_workflow(self):
        """Cancel the running workflow."""
        self._is_cancelled = True
        self.status_updated.emit("Cancelling workflow...")
        self.logger.info("Workflow cancellation requested")

def get_default_fitting_params() -> Dict[str, Any]:
    return {"model_params": {}}

def validate_fitting_params(params: Dict[str, Any]) -> Dict[str, Any]:
    validated = get_default_fitting_params()
    if "model_params" in params and isinstance(params["model_params"], dict):
        validated["model_params"] = params["model_params"].copy()
    return validated