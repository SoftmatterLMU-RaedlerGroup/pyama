from typing import Any
from pathlib import Path
import logging
import multiprocessing as mp
from PySide6.QtCore import QueueHandler
from .segmentation import SegmentationService
from .correction import CorrectionService
from .tracking import TrackingService
from .extraction import ExtractionService
from pyama_core.io.nikon import ND2Metadata

__all__ = ["process_fov_range"]


def process_fov_range(
    fov_indices: list[int],
    metadata: ND2Metadata,
    context: dict[str, Any],
    log_queue: mp.Queue,
) -> tuple[list[int], int, int, str]:
    """
    Process a range of FOVs through all steps (except copy).
    This function runs in a separate process.

    Args:
        fov_indices: List of FOV indices to process
        metadata: Raw-data metadata (ND2Metadata)
        context: User-specific processing context (channels, output_dir, npy_paths, params, ...)
        log_queue: Queue for logging from worker processes

    Returns:
        Tuple of (fov_indices, successful_count, failed_count, message)
    """
    # Set up logging in worker process to send to queue
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not root_logger.handlers:
        handler = QueueHandler(log_queue)
        root_logger.addHandler(handler)

    logger = logging.getLogger(__name__)

    successful_count = 0

    try:
        # Create services without Qt parent (for multiprocessing)
        segmentation = SegmentationService(None)
        correction = CorrectionService(None)
        tracking = TrackingService(None)
        trace_extraction = ExtractionService(None)

        # Resolve output directory from context
        output_dir = Path(context["output_dir"])  # type: ignore[arg-type]

        # Use process_all_fovs for each service
        logger.info(f"Processing FOVs {fov_indices[0]}-{fov_indices[-1]}")

        # Stage 1: Segmentation for all FOVs
        logger.info(
            f"Starting Segmentation for FOVs {fov_indices[0]}-{fov_indices[-1]}"
        )

        # Run segmentation; exceptions bubble up to outer handler
        segmentation.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1],
        )

        # Stage 2: Correction for all FOVs (always run now)
        logger.info(f"Starting Correction for FOVs {fov_indices[0]}-{fov_indices[-1]}")

        correction.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1],
        )

        # Stage 3: Cell tracking for all FOVs
        logger.info(f"Starting Tracking for FOVs {fov_indices[0]}-{fov_indices[-1]}")

        tracking.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1],
        )

        # Stage 4: Trace extraction for all FOVs
        logger.info(f"Starting Extraction for FOVs {fov_indices[0]}-{fov_indices[-1]}")

        trace_extraction.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1],
        )

        # All successful
        successful_count = len(fov_indices)
        success_msg = f"Completed processing FOVs {fov_indices[0]}-{fov_indices[-1]}"
        logger.info(f"{success_msg}")
        return fov_indices, successful_count, 0, success_msg

    except Exception as e:
        logger.exception(f"Error processing FOVs {fov_indices[0]}-{fov_indices[-1]}")
        error_msg = (
            f"Error processing FOVs {fov_indices[0]}-{fov_indices[-1]}: {str(e)}"
        )
        return fov_indices, 0, len(fov_indices), error_msg
