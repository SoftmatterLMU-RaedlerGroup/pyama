"""
Binarization processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
import numpy as np
from PySide6.QtCore import QObject

from .base import BaseProcessingService
from ..utils.binarization import logarithmic_std_binarization


class BinarizationService(BaseProcessingService):
    """Service for binarizing phase contrast microscopy images."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    def get_step_name(self) -> str:
        """Return the name of this processing step."""
        return "Binarization"

    def process_fov(
        self,
        fov_index: int,
        data_info: dict[str, Any],
        output_dir: Path,
        params: dict[str, Any],
    ) -> bool:
        """
        Process a single field of view: load phase contrast frames from NPY, binarize,
        and save binarized data as NPY.

        Args:
            fov_index: Field of view index to process
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters containing 'mask_size'

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract processing parameters
            mask_size = params.get("mask_size", 3)

            # Get metadata
            metadata: dict[str, Any] = data_info["metadata"]
            n_frames = metadata["n_frames"]
            height = metadata["height"]
            width = metadata["width"]
            base_name = data_info["filename"].replace(".nd2", "")

            # Get FOV directory
            fov_dir = output_dir / f"fov_{fov_index:04d}"
            
            # Check if phase contrast raw file exists
            pc_raw_path = fov_dir / f"{base_name}_fov{fov_index:04d}_phase_contrast_raw.npy"
            if not pc_raw_path.exists():
                error_msg = f"Phase contrast raw file not found: {pc_raw_path}"
                self.error_occurred.emit(error_msg)
                return False
            
            # Create output file path
            binarized_path = fov_dir / f"{base_name}_fov{fov_index:04d}_binarized.npy"

            # Load phase contrast data from NPY file
            self.status_updated.emit(f"FOV {fov_index}: Loading phase contrast data...")
            phase_contrast_data = np.load(pc_raw_path, mmap_mode='r')
            
            # Verify shape
            if phase_contrast_data.shape != (n_frames, height, width):
                error_msg = f"Unexpected shape for phase contrast data: {phase_contrast_data.shape}"
                self.error_occurred.emit(error_msg)
                return False

            # Define progress callback
            def progress_callback(frame_idx, n_frames, message):
                if self._is_cancelled:
                    raise InterruptedError("Processing cancelled")
                fov_progress = int((frame_idx + 1) / n_frames * 100)
                progress_msg = f"FOV {fov_index}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"
                
                # Log progress (every 30 frames)
                if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                    self.logger.info(progress_msg)

            # Binarize using the loaded phase contrast data
            status_msg = f"FOV {fov_index}: Applying binarization..."
            self.logger.info(status_msg)
            self.status_updated.emit(status_msg)
            
            try:
                # The logarithmic_std_binarization algorithm needs all frames for std calculation
                binarized_stack = logarithmic_std_binarization(
                    phase_contrast_data, mask_size, progress_callback
                )
            except InterruptedError:
                return False
            
            # Save binarized results as NPY
            self.status_updated.emit(f"FOV {fov_index}: Saving binarized data...")
            np.save(binarized_path, binarized_stack)

            self.status_updated.emit(f"FOV {fov_index} binarization completed")
            return True

        except Exception as e:
            error_msg = f"Error processing FOV {fov_index} in binarization: {str(e)}"
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
        n_fov = data_info["metadata"]["n_fov"]

        binarized_files = []

        for fov_idx in range(n_fov):
            fov_dir = output_dir / f"fov_{fov_idx:04d}"
            binarized_files.append(
                fov_dir / f"{base_name}_fov{fov_idx:04d}_binarized.npy"
            )

        return {"binarized": binarized_files}
