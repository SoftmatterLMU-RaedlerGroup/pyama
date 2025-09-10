"""
Workflow coordination for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from PySide6.QtCore import QObject
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import logging
from logging.handlers import QueueListener
from pyama_core.io.nikon import ND2Metadata

from .copying import CopyingService
from .steps import process_fov_range

logger = logging.getLogger(__name__)


class ProcessingWorkflow(QObject):
    """Coordinates parallel execution of processing workflow."""


    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.copy_service = CopyingService(self)
        self.log_queue_listener = None

    def run_complete_workflow(
        self,
        metadata: ND2Metadata,
        context: dict,
        fov_start: int | None = None,
        fov_end: int | None = None,
        batch_size: int = 4,
        n_workers: int = 4,
    ) -> bool:
        """
        Run the processing workflow with batch copy and parallel steps.

        Args:
            metadata: ND2Metadata describing the raw ND2 file.
            context: Processing context including keys: 'output_dir', 'params', 'channels', 'npy_paths'.
            fov_start: Starting FOV index (inclusive), None for 0.
            fov_end: Ending FOV index (inclusive), None for last FOV.
            batch_size: Number of FOVs to process per batch.
            n_workers: Number of parallel worker processes.

        Returns:
            True if all FOVs completed successfully; False otherwise.
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
            # Ensure output directory exists (from context)
            output_dir = Path(context["output_dir"])  # type: ignore[arg-type]
            output_dir.mkdir(parents=True, exist_ok=True)

            # Determine total FOVs from metadata
            n_fov = int(metadata.n_fovs)

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
                logger.error(error_msg)
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

                # Stage 1: Extract batch from ND2 to NPY (context-aware)
                try:
                    self.copy_service.process_all_fovs(
                        metadata=metadata,
                        context=context,
                        output_dir=output_dir,
                        fov_start=batch_fovs[0],
                        fov_end=batch_fovs[-1],
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to extract batch starting at FOV {batch_fovs[0]}: {e}"
                    )
                    return False

                # Stage 2: Process extracted FOVs in parallel
                logger.info(f"Processing batch in parallel with {n_workers} workers")

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
                                metadata,
                                context,
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

                                completed_fovs += successful

                                if failed > 0:
                                    logger.error(
                                        f"{failed} FOVs failed in range {fov_indices_res[0]}-{fov_indices_res[-1]}"
                                    )

                            except Exception as e:
                                error_msg = f"Worker exception for FOVs {fov_range[0]}-{fov_range[-1]}: {str(e)}"
                                logger.error(error_msg)

                            # Update overall progress
                            progress = int(completed_fovs / total_fovs * 100)
                            logger.info(f"Progress: {progress}%")
                finally:
                    pass

            overall_success = completed_fovs == total_fovs
            msg = f"Completed processing {completed_fovs}/{total_fovs} FOVs"
            logger.info(msg)
            return overall_success

        except Exception as e:
            error_msg = f"Error in parallel workflow: {str(e)}"
            logger.exception(error_msg)
            return False

        finally:
            if self.log_queue_listener:
                self.log_queue_listener.stop()
