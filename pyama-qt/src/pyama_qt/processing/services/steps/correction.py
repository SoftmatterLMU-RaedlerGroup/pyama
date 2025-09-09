"""
Correction processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
import numpy as np
from PySide6.QtCore import QObject
from numpy.lib.format import open_memmap

from ..base import BaseProcessingService
from pyama_core.processing.background import correct_bg
import logging

logger = logging.getLogger(__name__)


class CorrectionService(BaseProcessingService):
    """Service for correction of fluorescence microscopy images."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.name = "Correction"

    def process_fov(
        self,
        metadata: dict[str, Any],
        context: dict[str, Any],
        output_dir: Path,
        fov: int,
    ) -> None:
        """
        Process a single field of view: load fluorescence from NPY and segmentation,
        perform temporal background correction, and save corrected fluorescence data.

        Args:
            metadata: Metadata from file loading
            context: Context for the processing
            output_dir: Output directory for results
            fov: Field of view index to process

        Returns:
            None
        """
        try:
            # Parameters are currently not configurable via UI

            # Load NPY data and derive dimensions directly from arrays
            base_name = metadata["filename"].replace(".nd2", "")

            # Use FOV subdirectory
            fov_dir = output_dir / f"fov_{fov:04d}"

            # Check if fluorescence raw file exists
            fl_raw_path = fov_dir / f"{base_name}_fov{fov:04d}_fluorescence_raw.npy"
            if not fl_raw_path.exists():
                # If no fluorescence channel, skip background correction
                logger.info(
                    f"FOV {fov}: No fluorescence channel, skipping background correction"
                )
                return

            # Create output file path in FOV subdirectory
            corrected_path = (
                fov_dir / f"{base_name}_fov{fov:04d}_fluorescence_corrected.npy"
            )

            # Load segmentation data from FOV subdirectory
            segmentation_path = fov_dir / f"{base_name}_fov{fov:04d}_binarized.npy"
            if not segmentation_path.exists():
                raise FileNotFoundError(
                    f"Segmentation data not found: {segmentation_path}"
                )

            # Load segmentation data (memory-mapped .npy file)
            logger.info(f"FOV {fov}: Loading segmentation data...")
            segmentation_data = open_memmap(segmentation_path, mode="r")

            # Load fluorescence data from NPY file (memory-mapped)
            logger.info(f"FOV {fov}: Loading fluorescence data...")
            fluor_data = open_memmap(fl_raw_path, mode="r")

            # Derive dimensions from the loaded arrays and verify they match
            if fluor_data.ndim != 3:
                raise ValueError(
                    f"Unexpected fluorescence data dims: {fluor_data.shape}"
                )
            n_frames, height, width = (
                int(fluor_data.shape[0]),
                int(fluor_data.shape[1]),
                int(fluor_data.shape[2]),
            )

            if segmentation_data.shape != (n_frames, height, width):
                error_msg = (
                    f"Unexpected shape for segmentation data: {segmentation_data.shape}"
                )
                raise ValueError(error_msg)

            # Create output memory-mapped array
            corrected_memmap = None
            corrected_memmap = open_memmap(
                corrected_path,
                mode="w+",
                dtype=np.float32,
                shape=(n_frames, height, width),
            )

            # Define progress callback
            def progress_callback(frame_idx, n_frames, message):
                fov_progress = int((frame_idx + 1) / n_frames * 100)
                progress_msg = f"FOV {fov}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"

                # Log progress (every 30 frames)
                if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                    logger.info(progress_msg)

            # Perform background correction using selected method
            status_msg = f"FOV {fov}: Starting temporal background correction..."
            logger.info(status_msg)

            try:
                # Single algorithm implementation: tile-based interpolation correction
                # The functional API writes into the provided output array
                correct_bg(
                    fluor_data.astype(np.float32),
                    segmentation_data,
                    corrected_memmap,
                    progress_callback=progress_callback,
                )
            except InterruptedError:
                if corrected_memmap is not None:
                    del corrected_memmap
                raise

            logger.info(f"FOV {fov}: Cleaning up...")
            if corrected_memmap is not None:
                del corrected_memmap

            logger.info(f"FOV {fov} background correction completed")

        except Exception as e:
            error_msg = f"Error processing FOV {fov} in background correction: {str(e)}"
            logger.error(error_msg)
            raise
