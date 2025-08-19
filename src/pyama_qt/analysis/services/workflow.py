"""
Workflow coordination for parallel trace fitting analysis.

Manages parallel execution of fitting across multiple FOVs.
"""

from pathlib import Path
from PySide6.QtCore import QObject, Signal
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import logging
from logging.handlers import QueueListener
from typing import Dict, Any, Optional

from .fitting_worker import process_fov_batch
from pyama_qt.core.csv_loader import (
    create_fov_batches,
    discover_trace_files,
    discover_simple_csv_files,
    create_simple_csv_batches,
    process_simple_csv_batch,
)
from pyama_qt.core.logging_config import get_logger


class AnalysisWorkflowCoordinator(QObject):
    """Coordinates parallel execution of trace fitting workflow."""

    progress_updated = Signal(int)  # Overall progress percentage (0-100)
    status_updated = Signal(str)  # Status message
    error_occurred = Signal(str)  # Error message
    fov_completed = Signal(str, dict)  # FOV name, results summary

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_cancelled = False
        self.logger = get_logger(__name__)
        self.log_queue_listener = None

    def run_fitting_workflow(
        self,
        data_folder: Path,
        model_type: str,
        fitting_params: Dict[str, Any],
        batch_size: int = 10,
        n_workers: int = 4,
        data_format: str = "auto",
    ) -> bool:
        """
        Run the trace fitting workflow with parallel processing.

        Args:
            data_folder: Root folder containing FOV subdirectories with trace CSVs
                        OR path to a simple CSV file/directory of CSV files
            model_type: Type of model to fit ('maturation', 'twostage', 'trivial')
            fitting_params: Dictionary of fitting parameters including:
                - model_params: Model-specific parameter overrides
            batch_size: Number of FOVs to process per worker batch
            n_workers: Number of parallel workers
            data_format: 'fov' for FOV-based traces, 'simple' for simple CSV,
                        'auto' to detect automatically

        Returns:
            bool: True if workflow completed successfully
        """
        self._is_cancelled = False
        overall_success = False

        # Set up logging queue for worker processes
        log_queue = mp.Manager().Queue()

        handlers = logging.getLogger().handlers
        if not handlers:
            logging.basicConfig(level=logging.INFO)
            handlers = logging.getLogger().handlers

        self.log_queue_listener = QueueListener(log_queue, *handlers)
        self.log_queue_listener.start()

        try:
            self.status_updated.emit("Discovering trace files...")

            # Detect data format if auto
            if data_format == "auto":
                # Check if it's a single CSV file
                if data_folder.is_file() and data_folder.suffix.lower() == ".csv":
                    data_format = "simple"
                # Check for FOV directories
                elif any(
                    d.name.startswith("fov_")
                    for d in data_folder.iterdir()
                    if d.is_dir()
                ):
                    data_format = "fov"
                # Default to simple CSV for directory of CSV files
                else:
                    data_format = "simple"

                self.logger.info(f"Auto-detected data format: {data_format}")

            # Discover files based on format
            if data_format == "fov":
                # Original FOV-based discovery
                trace_files = discover_trace_files(data_folder)
                if not trace_files:
                    error_msg = f"No FOV trace CSV files found in {data_folder}"
                    self.error_occurred.emit(error_msg)
                    return False

                self.logger.info(f"Found {len(trace_files)} FOVs with trace files")
                self.status_updated.emit(f"Found {len(trace_files)} FOVs to process")

                # Create batches for parallel processing
                fov_batches = create_fov_batches(trace_files, batch_size)
                process_func = process_fov_batch

            else:  # simple CSV format
                # Simple CSV discovery
                csv_files = discover_simple_csv_files(data_folder)
                if not csv_files:
                    error_msg = f"No CSV files found in {data_folder}"
                    self.error_occurred.emit(error_msg)
                    return False

                self.logger.info(f"Found {len(csv_files)} CSV file(s) to process")
                self.status_updated.emit(
                    f"Found {len(csv_files)} dataset(s) to process"
                )

                # Create batches for parallel processing
                fov_batches = create_simple_csv_batches(csv_files, batch_size)
                process_func = process_simple_csv_batch

            self.logger.info(
                f"Created {len(fov_batches)} batches for {n_workers} workers"
            )
            self.status_updated.emit(
                f"Starting parallel fitting with {n_workers} workers..."
            )

            # Process batches in parallel
            with ProcessPoolExecutor(max_workers=n_workers) as executor:
                # Submit all batches
                future_to_batch = {}
                for i, batch in enumerate(fov_batches):
                    future = executor.submit(
                        process_func, batch, model_type, fitting_params, log_queue
                    )
                    future_to_batch[future] = (i, batch)

                # Process completed batches
                completed_batches = 0
                total_successful_fits = 0
                total_failed_fits = 0
                all_errors = []

                for future in as_completed(future_to_batch):
                    if self._is_cancelled:
                        self.logger.info("Workflow cancelled by user")
                        return False

                    batch_idx, batch = future_to_batch[future]

                    try:
                        batch_result = future.result()

                        # Update statistics
                        total_successful_fits += batch_result["successful_fits"]
                        total_failed_fits += batch_result["failed_fits"]
                        all_errors.extend(batch_result["processing_errors"])

                        # Emit signals for each FOV in the batch
                        for fov_name, fov_result in batch_result["fov_results"].items():
                            self.fov_completed.emit(fov_name, fov_result)

                        completed_batches += 1
                        progress = int((completed_batches / len(fov_batches)) * 100)
                        self.progress_updated.emit(progress)

                        batch_fovs = [fov_name for fov_name, _ in batch]
                        self.status_updated.emit(
                            f"Completed batch {completed_batches}/{len(fov_batches)} "
                            f"(FOVs: {', '.join(batch_fovs)})"
                        )

                        self.logger.info(
                            f"Batch {batch_idx + 1} completed: "
                            f"{batch_result['successful_fits']}/{batch_result['total_cells']} successful fits"
                        )

                    except Exception as e:
                        error_msg = f"Error processing batch {batch_idx + 1}: {str(e)}"
                        self.logger.exception(error_msg)
                        self.error_occurred.emit(error_msg)
                        all_errors.append(error_msg)

            # Final status
            total_cells = total_successful_fits + total_failed_fits
            success_rate = (
                (total_successful_fits / total_cells * 100) if total_cells > 0 else 0
            )

            final_message = (
                f"Fitting completed: {total_successful_fits}/{total_cells} cells "
                f"({success_rate:.1f}% success rate)"
            )

            self.status_updated.emit(final_message)
            self.logger.info(final_message)

            if all_errors:
                self.logger.warning(
                    f"Encountered {len(all_errors)} errors during processing"
                )
                # Emit first few errors as warnings
                for error in all_errors[:5]:
                    self.error_occurred.emit(f"Warning: {error}")

            overall_success = total_successful_fits > 0

        except Exception as e:
            error_msg = f"Critical error in fitting workflow: {str(e)}"
            self.logger.exception(error_msg)
            self.error_occurred.emit(error_msg)
            overall_success = False

        finally:
            # Clean up logging
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
    """
    Get default fitting parameters.

    Returns:
        Dictionary of default fitting parameters
    """
    return {"model_params": {}}


def validate_fitting_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize fitting parameters.

    Args:
        params: Input parameters dictionary

    Returns:
        Validated parameters dictionary
    """
    validated = get_default_fitting_params()

    # Update with provided parameters

    if "model_params" in params and isinstance(params["model_params"], dict):
        validated["model_params"] = params["model_params"].copy()

    return validated
