"""
Background correction processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
import numpy as np
from PySide6.QtCore import QObject
from numpy.lib.format import open_memmap

from .base import BaseProcessingService
from pyama_core.processing.background import correct_bg
import logging

logger = logging.getLogger(__name__)

class BackgroundService(BaseProcessingService):
    """Service for background correction of fluorescence microscopy images."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.name = "Background"

    def process_fov(
        self,
        fov_index: int,
        data_info: dict[str, Any],
        output_dir: Path,
    ) -> bool:
        """
        Process a single field of view: load fluorescence from NPY and segmentation,
        perform temporal background correction, and save corrected fluorescence data.

        Args:
            fov_index: Field of view index to process
            data_info: Metadata from file loading
            output_dir: Output directory for results

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Parameters are currently not configurable via UI

            # Load NPY data and derive dimensions directly from arrays
            base_name = data_info["filename"].replace(".nd2", "")

            # Use FOV subdirectory
            fov_dir = output_dir / f"fov_{fov_index:04d}"

            # Check if fluorescence raw file exists
            fl_raw_path = (
                fov_dir / f"{base_name}_fov{fov_index:04d}_fluorescence_raw.npy"
            )
            if not fl_raw_path.exists():
                # If no fluorescence channel, skip background correction
                self.status_updated.emit(
                    f"FOV {fov_index}: No fluorescence channel, skipping background correction"
                )
                return True

            # Create output file path in FOV subdirectory
            corrected_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "fluorescence_corrected"
            )

            # Load segmentation data from FOV subdirectory
            segmentation_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "binarized"
            )
            if not segmentation_path.exists():
                raise FileNotFoundError(
                    f"Segmentation data not found: {segmentation_path}"
                )

            # Load segmentation data (memory-mapped .npy file)
            self.status_updated.emit(f"FOV {fov_index}: Loading segmentation data...")
            segmentation_data = open_memmap(segmentation_path, mode="r")

            # Load fluorescence data from NPY file (memory-mapped)
            self.status_updated.emit(f"FOV {fov_index}: Loading fluorescence data...")
            fluor_data = open_memmap(fl_raw_path, mode="r")

            # Derive dimensions from the loaded arrays and verify they match
            if fluor_data.ndim != 3:
                self.error_occurred.emit(
                    f"Unexpected fluorescence data dims: {fluor_data.shape}"
                )
                return False
            n_frames, height, width = int(fluor_data.shape[0]), int(fluor_data.shape[1]), int(fluor_data.shape[2])

            if segmentation_data.shape != (n_frames, height, width):
                error_msg = (
                    f"Unexpected shape for segmentation data: {segmentation_data.shape}"
                )
                self.error_occurred.emit(error_msg)
                return False

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
                progress_msg = f"FOV {fov_index}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"

                # Log progress (every 30 frames)
                if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                    logger.info(progress_msg)

            # Perform background correction using selected method
            status_msg = f"FOV {fov_index}: Starting temporal background correction..."
            logger.info(status_msg)
            self.status_updated.emit(status_msg)

            try:
                # Single algorithm implementation: tile-based interpolation correction
                # The functional API writes into the provided output array
                correct_bg(
                    fluor_data.astype(np.float32), segmentation_data, corrected_memmap, progress_callback=progress_callback
                )
            except InterruptedError:
                if corrected_memmap is not None:
                    del corrected_memmap
                return False

            self.status_updated.emit(f"FOV {fov_index}: Cleaning up...")
            if corrected_memmap is not None:
                del corrected_memmap

            self.status_updated.emit(f"FOV {fov_index} background correction completed")
            return True

        except Exception as e:
            error_msg = (
                f"Error processing FOV {fov_index} in background correction: {str(e)}"
            )
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

        corrected_files = []

        for fov_idx in range(n_fov):
            fov_dir = output_dir / f"fov_{fov_idx:04d}"
            corrected_files.append(
                fov_dir
                / self.get_output_filename(base_name, fov_idx, "fluorescence_corrected")
            )

        return {"fluorescence_corrected": corrected_files}

    def requires_previous_step(self) -> str | None:
        """
        Return the name of the required previous processing step.

        Returns:
            str: Name of required previous step (segmentation for masks)
        """
        return "Segmentation"
