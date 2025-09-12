from __future__ import annotations

import logging

from pyama_core.workflow.services.steps.segmentation import SegmentationService
from pyama_core.workflow.services.steps.correction import CorrectionService
from pyama_core.workflow.services.steps.tracking import TrackingService
from pyama_core.workflow.services.steps.extraction import ExtractionService
from pyama_core.io.nikon import ND2Metadata
from pyama_core.workflow import ProcessingContext


__all__ = ["process_fov_range"]


def process_fov_range(
    fov_indices: list[int],
    metadata: ND2Metadata,
    context: ProcessingContext,
) -> tuple[list[int], int, int, str]:
    logger = logging.getLogger(__name__)
    successful_count = 0

    try:
        segmentation = SegmentationService()
        correction = CorrectionService()
        tracking = TrackingService()
        trace_extraction = ExtractionService()

        output_dir = context["output_dir"]

        logger.info(f"Processing FOVs {fov_indices[0]}-{fov_indices[-1]}")

        logger.info(
            f"Starting Segmentation for FOVs {fov_indices[0]}-{fov_indices[-1]}"
        )
        segmentation.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1],
        )

        logger.info(f"Starting Correction for FOVs {fov_indices[0]}-{fov_indices[-1]}")
        correction.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1],
        )

        logger.info(f"Starting Tracking for FOVs {fov_indices[0]}-{fov_indices[-1]}")
        tracking.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1],
        )

        logger.info(f"Starting Extraction for FOVs {fov_indices[0]}-{fov_indices[-1]}")
        trace_extraction.process_all_fovs(
            metadata=metadata,
            context=context,
            output_dir=output_dir,
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1],
        )

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
