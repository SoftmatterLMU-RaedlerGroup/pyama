"""
Workflow coordination for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from PySide6.QtCore import QObject, Signal
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import logging
from logging.handlers import QueueListener
from typing import Any

from .copying import CopyingService
from .steps import process_fov_range

logger = logging.getLogger(__name__)


class ProcessingWorkflow(QObject):
    """Coordinates parallel execution of processing workflow."""

    progress_updated = Signal(int)  # Overall progress percentage
    status_updated = Signal(str)  # Status message
    error_occurred = Signal(str)  # Error message

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.copy_service = CopyingService(self)
        self.log_queue_listener = None

    def run_complete_workflow(
        self,
        nd2_path: str,
        data_info: dict[str, Any],
        output_dir: Path,
        params: dict[str, Any],
        fov_start: int | None = None,
        fov_end: int | None = None,
        batch_size: int = 4,
        n_workers: int = 4,
    ) -> bool:
        """
        Run the processing workflow with batch extraction and parallel processing.

        Args:
            nd2_path: Path to ND2 file
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters
            fov_start: Starting FOV index (inclusive), None for 0
            fov_end: Ending FOV index (inclusive), None for last FOV
            batch_size: Number of FOVs to extract at once
            n_workers: Number of parallel workers for processing

        Returns:
            bool: True if all steps completed successfully
        """
        overall_success = False

        # Set up logging queue and listener for worker processes
        log_queue = mp.Manager().Queue()

        # Use handlers from the root logger
        handlers = logging.getLogger().handlers
        if not handlers:
            # If no handlers are configured, add a basic one
            logging.basicConfig(level=logging.INFO)
            handlers = logging.getLogger().handlers

        self.log_queue_listener = QueueListener(log_queue, *handlers)
        self.log_queue_listener.start()

        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            meta = data_info.get("metadata", {})
            n_fov = int(data_info.get("n_fov", meta.get("n_fov", 0)))

            # Determine FOV range
            if fov_start is None:
                fov_start = 0
            if fov_end is None:
                fov_end = n_fov - 1

            # Validate range
            if fov_start < 0 or fov_end >= n_fov or fov_start > fov_end:
                error_msg = (
                    f"Invalid FOV range: {fov_start}-{fov_end} (file has {n_fov} FOVs)"
                )
                self.error_occurred.emit(error_msg)
                return False

            total_fovs = fov_end - fov_start + 1
            fov_indices = list(range(fov_start, fov_end + 1))

            # Process in batches
            completed_fovs = 0

            for batch_start in range(0, total_fovs, batch_size):
                # Get current batch
                batch_end = min(batch_start + batch_size, total_fovs)
                batch_fovs = fov_indices[batch_start:batch_end]

                logger.info(f"Extracting batch: FOVs {batch_fovs[0]}-{batch_fovs[-1]}")
                self.status_updated.emit(
                    f"Extracting batch: FOVs {batch_fovs[0]}-{batch_fovs[-1]}"
                )

                # Stage 1: Extract batch from ND2 to NPY
                extraction_success = self.copy_service.process_batch(
                    nd2_path, batch_fovs, data_info, output_dir
                )

                if not extraction_success:
                    self.error_occurred.emit(
                        f"Failed to extract batch starting at FOV {batch_fovs[0]}"
                    )
                    return False

                # Stage 2: Process extracted FOVs in parallel
                logger.info(f"Processing batch in parallel with {n_workers} workers")
                self.status_updated.emit(
                    f"Processing batch in parallel with {n_workers} workers"
                )

                try:
                    ctx = mp.get_context("spawn")
                    with ProcessPoolExecutor(
                        max_workers=n_workers, mp_context=ctx
                    ) as executor:
                        # Distribute FOVs among workers
                        fovs_per_worker = len(batch_fovs) // n_workers
                        remainder = len(batch_fovs) % n_workers

                        # Create FOV ranges for each worker
                        worker_ranges = []
                        start_idx = 0
                        for i in range(n_workers):
                            count = fovs_per_worker + (1 if i < remainder else 0)
                            if count > 0:
                                end_idx = start_idx + count
                                worker_ranges.append(batch_fovs[start_idx:end_idx])
                                start_idx = end_idx

                        # Submit ranges to workers
                        futures = {
                            executor.submit(
                                process_fov_range,
                                fov_range,
                                data_info,
                                output_dir,
                                params,
                                log_queue,
                            ): fov_range
                            for fov_range in worker_ranges
                            if fov_range
                        }

                        # Track completion
                        for future in as_completed(futures):
                            fov_range = futures[future]
                            try:
                                fov_indices_res, successful, failed, message = (
                                    future.result()
                                )
                                logger.info(message)
                                self.status_updated.emit(message)

                                completed_fovs += successful

                                if failed > 0:
                                    self.error_occurred.emit(
                                        f"{failed} FOVs failed in range {fov_indices_res[0]}-{fov_indices_res[-1]}"
                                    )

                            except Exception as e:
                                error_msg = f"Worker exception for FOVs {fov_range[0]}-{fov_range[-1]}: {str(e)}"
                                logger.error(error_msg)
                                self.error_occurred.emit(error_msg)

                            # Update overall progress
                            progress = int(completed_fovs / total_fovs * 100)
                            self.progress_updated.emit(progress)
                finally:
                    pass

                # Optional: Clean up raw NPY files after successful processing
                if params.get("delete_raw_after_processing", False):
                    self._cleanup_raw_files(batch_fovs, data_info, output_dir)

            overall_success = completed_fovs == total_fovs
            msg = f"Completed processing {completed_fovs}/{total_fovs} FOVs"
            logger.info(msg)
            self.status_updated.emit(msg)
            return overall_success

        except Exception as e:
            error_msg = f"Error in parallel workflow: {str(e)}"
            logger.exception(error_msg)
            self.error_occurred.emit(error_msg)
            return False

        finally:
            if self.log_queue_listener:
                self.log_queue_listener.stop()

    def _cleanup_raw_files(
        self, fov_indices: list[int], data_info: dict[str, Any], output_dir: Path
    ):
        """Delete raw NPY files after successful processing."""
        base_name = data_info["filename"].replace(".nd2", "")

        for fov_idx in fov_indices:
            fov_dir = output_dir / f"fov_{fov_idx:04d}"

            # Delete raw files
            pc_raw = fov_dir / f"{base_name}_fov{fov_idx:04d}_phase_contrast_raw.npy"
            fl_raw = fov_dir / f"{base_name}_fov{fov_idx:04d}_fluorescence_raw.npy"

            if pc_raw.exists():
                pc_raw.unlink()
            if fl_raw.exists():
                fl_raw.unlink()

            logger.debug(f"Cleaned up raw files for FOV {fov_idx}")

    def get_all_services(self) -> list:
        """Get all processing services for signal connection."""
        # Only return the copy service since other services run in separate processes
        return [self.copy_service]


class WorkflowWorker(QObject):
    """Worker class for running workflow processing in a separate thread."""

    finished = Signal(bool, str)  # success, message

    def __init__(self, workflow_coordinator, nd2_path, data_info, output_dir, params):
        super().__init__()
        self.workflow_coordinator = workflow_coordinator
        self.nd2_path = nd2_path
        self.data_info = data_info
        self.output_dir = output_dir
        self.params = params

    def run_processing(self):
        """Run the workflow processing."""
        try:
            # Extract FOV and batch parameters
            fov_start = self.params.get("fov_start", 0)
            fov_end = self.params.get("fov_end", None)
            batch_size = self.params.get("batch_size", 4)
            n_workers = self.params.get("n_workers", 4)

            success = self.workflow_coordinator.run_complete_workflow(
                self.nd2_path,
                self.data_info,
                self.output_dir,
                self.params,
                fov_start=fov_start,
                fov_end=fov_end,
                batch_size=batch_size,
                n_workers=n_workers,
            )

            if success:
                self.finished.emit(True, f"Results saved to {self.output_dir}")
            else:
                self.finished.emit(False, "Workflow failed")

        except Exception as e:
            self.finished.emit(False, f"Workflow error: {str(e)}")
