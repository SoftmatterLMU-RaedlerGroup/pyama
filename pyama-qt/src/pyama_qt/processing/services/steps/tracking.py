"""
Cell tracking processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
import numpy as np
from numpy.lib.format import open_memmap
from PySide6.QtCore import QObject

from ..base import BaseProcessingService
from pyama_core.processing.tracking import track_cell
from pyama_core.io.nikon import ND2Metadata
import logging

logger = logging.getLogger(__name__)


class TrackingService(BaseProcessingService):
    """Service for tracking cells across time frames using IoU-based assignment."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.name = "Tracking"

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: dict[str, Any],
        output_dir: Path,
        fov: int,
    ) -> None:
        """
        Process a single field of view: load binary segmentation data,
        perform tracking, and save seg_labeled to NPY file.

        Args:
            metadata: Metadata from file loading
            context: Context for the processing
            output_dir: Output directory for results
            fov: Field of view index to process

        Returns:
            None
        """
        try:
            base_name = metadata.base_name

            load_msg = f"FOV {fov}: Loading segmentation data..."
            logger.info(load_msg)

            # Use FOV subdirectory
            fov_dir = output_dir / f"fov_{fov:04d}"

            # Load binary segmentation data from FOV subdirectory
            segmentation_path = fov_dir / f"{base_name}_fov{fov:04d}_binarized.npy"
            if not segmentation_path.exists():
                raise FileNotFoundError(
                    f"Binary segmentation data not found: {segmentation_path}"
                )

            segmentation_data = open_memmap(segmentation_path, mode="r")

            # Create output array for tracking labels
            n_frames, height, width = segmentation_data.shape
            seg_labeled = np.zeros((n_frames, height, width), dtype=np.uint16)

            # Define progress callback
            def progress_callback(frame_idx, n_frames, message):
                fov_progress = int((frame_idx + 1) / n_frames * 100)
                progress_msg = f"FOV {fov}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"

                # Log progress (every 30 frames)
                if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                    logger.info(progress_msg)

            # Perform cell tracking
            status_msg = f"FOV {fov}: Starting cell tracking..."
            logger.info(status_msg)

            try:
                track_cell(
                    image=segmentation_data,
                    out=seg_labeled,
                    progress_callback=progress_callback,
                )
            except InterruptedError:
                raise

            # Save tracked labels to NPY file in FOV subdirectory
            seg_labeled_path = fov_dir / f"{base_name}_fov{fov:04d}_seg_labeled.npy"
            np.save(seg_labeled_path, seg_labeled)

            complete_msg = f"FOV {fov} cell tracking completed"
            logger.info(complete_msg)

        except Exception as e:
            error_msg = f"Error processing FOV {fov} in cell tracking: {str(e)}"
            logger.error(error_msg)
            raise
