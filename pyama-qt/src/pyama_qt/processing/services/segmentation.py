"""
Segmentation (formerly binarization) service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
import numpy as np
from PySide6.QtCore import QObject

from .base import BaseProcessingService
from pyama_core.processing.segmentation import segment_cell
import logging

logger = logging.getLogger(__name__)


class SegmentationService(BaseProcessingService):
    """Service for segmenting phase contrast microscopy images."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.name = "Segmentation"

    def process_fov(
        self,
        fov_index: int,
        data_info: dict[str, Any],
        output_dir: Path,
    ) -> bool:
        """
        Process a single field of view: load phase contrast frames from NPY, segment,
        and save segmentation data as NPY.

        Args:
            fov_index: Field of view index to process
            data_info: Metadata from file loading
            output_dir: Output directory for results

        Returns:
            bool: True if successful, False otherwise
        """
        try:

            # Use array shapes directly rather than metadata for dims
            base_name = data_info["filename"].replace(".nd2", "")

            # Get FOV directory
            fov_dir = output_dir / f"fov_{fov_index:04d}"

            # Check if phase contrast raw file exists
            pc_raw_path = (
                fov_dir / f"{base_name}_fov{fov_index:04d}_phase_contrast_raw.npy"
            )
            if not pc_raw_path.exists():
                error_msg = f"Phase contrast raw file not found: {pc_raw_path}"
                self.error_occurred.emit(error_msg)
                return False

            # Create output file path
            binarized_path = fov_dir / f"{base_name}_fov{fov_index:04d}_binarized.npy"

            # Load phase contrast data from NPY file
            self.status_updated.emit(f"FOV {fov_index}: Loading phase contrast data...")
            phase_contrast_data = np.load(pc_raw_path, mmap_mode="r")

            # Derive dimensions from the loaded array and validate 3D shape
            if phase_contrast_data.ndim != 3:
                error_msg = f"Unexpected dims for phase contrast data: {phase_contrast_data.shape}"
                self.error_occurred.emit(error_msg)
                return False
            n_frames, height, width = (
                int(phase_contrast_data.shape[0]),
                int(phase_contrast_data.shape[1]),
                int(phase_contrast_data.shape[2]),
            )

            # Define progress callback
            def progress_callback(frame_idx, n_frames, message):
                fov_progress = int((frame_idx + 1) / n_frames * 100)
                progress_msg = f"FOV {fov_index}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"

                # Log progress (every 30 frames)
                if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                    logger.info(progress_msg)

            # Binarize using the selected algorithm
            status_msg = f"FOV {fov_index}: Applying segmentation..."
            logger.info(status_msg)
            self.status_updated.emit(status_msg)

            # Single-seeded segmentation algorithm: log-std
            try:
                # Preallocate boolean output and call the single algorithm
                binarized_stack = np.zeros(phase_contrast_data.shape, dtype=bool)
                segment_cell(phase_contrast_data, binarized_stack, progress_callback=progress_callback)
            except InterruptedError:
                return False

            # Save segmentation results as NPY
            self.status_updated.emit(f"FOV {fov_index}: Saving segmentation data...")
            np.save(binarized_path, binarized_stack)

            self.status_updated.emit(f"FOV {fov_index} segmentation completed")
            return True

        except Exception as e:
            error_msg = f"Error processing FOV {fov_index} in segmentation: {str(e)}"
            self.error_occurred.emit(error_msg)
            return False

    def get_expected_outputs(
        self, data_info: dict[str, Any], output_dir: Path
    ) -> dict[str, list]:
        """
        Get expected output files for this processing step.

        Args:
            data_info: Metadata from file loading
            output_dir: Output directory

        Returns:
            Dict with lists of expected output file paths
        """
        base_name = data_info["filename"].replace(".nd2", "")
        meta = data_info.get("metadata", {})
        n_fov = int(data_info.get("n_fov", meta.get("n_fov", 0)))

        binarized_files = []

        for fov_idx in range(n_fov):
            fov_dir = output_dir / f"fov_{fov_idx:04d}"
            binarized_files.append(
                fov_dir / f"{base_name}_fov{fov_idx:04d}_binarized.npy"
            )

        return {"binarized": binarized_files}
