"""
Cell tracking processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
import numpy as np
from numpy.lib.format import open_memmap
from PySide6.QtCore import QObject

from .base import BaseProcessingService
from pyama_core.processing.tracking import track_cell
import logging

logger = logging.getLogger(__name__)


class TrackingService(BaseProcessingService):
    """Service for tracking cells across time frames using IoU-based assignment."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.name = "Tracking"

    def process_fov(
        self,
        fov_index: int,
        data_info: dict[str, Any],
        output_dir: Path,
    ) -> bool:
        """
        Process a single field of view: load binary segmentation data,
        perform tracking, and save seg_labeled to NPY file.

        Args:
            fov_index: Field of view index to process
            data_info: Metadata from file loading
            output_dir: Output directory for results

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            base_name = data_info["filename"].replace(".nd2", "")

            load_msg = f"FOV {fov_index}: Loading segmentation data..."
            logger.info(load_msg)
            self.status_updated.emit(load_msg)

            # Use FOV subdirectory
            fov_dir = output_dir / f"fov_{fov_index:04d}"

            # Load binary segmentation data from FOV subdirectory
            segmentation_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "binarized"
            )
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
                progress_msg = f"FOV {fov_index}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"

                # Log progress (every 30 frames)
                if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                    logger.info(progress_msg)
                
                self.status_updated.emit(progress_msg)

            # Perform cell tracking
            status_msg = f"FOV {fov_index}: Starting cell tracking..."
            logger.info(status_msg)
            self.status_updated.emit(status_msg)
            
            try:
                track_cell(
                    image=segmentation_data,
                    out=seg_labeled,
                    progress_callback=progress_callback,
                )
            except InterruptedError:
                return False

            # Save tracked labels to NPY file in FOV subdirectory
            seg_labeled_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "seg_labeled"
            )
            np.save(seg_labeled_path, seg_labeled)

            complete_msg = f"FOV {fov_index} cell tracking completed"
            logger.info(complete_msg)
            self.status_updated.emit(complete_msg)
            return True

        except Exception as e:
            error_msg = (
                f"Error processing FOV {fov_index} in cell tracking: {str(e)}"
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

        seg_labeled_files = []

        for fov_idx in range(n_fov):
            fov_dir = output_dir / f"fov_{fov_idx:04d}"
            seg_labeled_files.append(
                fov_dir / self.get_output_filename(base_name, fov_idx, "seg_labeled")
            )

        return {"seg_labeled": seg_labeled_files}

    def requires_previous_step(self) -> str | None:
        """
        Return the name of the required previous processing step.

        Returns:
            str: Name of required previous step
        """
        return "Segmentation"