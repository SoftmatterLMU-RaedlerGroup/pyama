"""
Segmentation (formerly binarization) service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
import numpy as np
from PySide6.QtCore import QObject
from functools import partial

from ..base import BaseProcessingService
from pyama_core.io.nikon import ND2Metadata
from pyama_core.processing.segmentation import segment_cell
import logging

logger = logging.getLogger(__name__)


class SegmentationService(BaseProcessingService):
    """Service for segmenting phase contrast microscopy images.

    Context contract (read):
    - Read: context["npy_paths"][fov]["phase_contrast"] if available;
            otherwise falls back to standard file path.
    - Optional: context["channels"]["phase_contrast"] for diagnostics.
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.name = "Segmentation"

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: dict[str, Any],
        output_dir: Path,
        fov: int,
    ) -> None:
        """
        Process a single field of view: load phase contrast frames from NPY, segment,
        and save segmentation data as NPY.

        Args:
            metadata: Metadata from file loading
            context: Context for the processing
            output_dir: Output directory for results
            fov: Field of view index to process

        Returns:
            None
        """
        try:
            # Use ND2Metadata-provided base name
            basename = metadata.base_name

            # Get FOV directory
            fov_dir = output_dir / f"fov_{fov:04d}"

            # Resolve phase-contrast path from context if provided; otherwise fallback to default naming
            pc_raw_path = None
            try:
                pc_raw_path = context.get("npy_paths", {}).get(fov, {}).get("phase_contrast")
            except Exception:
                pc_raw_path = None

            if pc_raw_path is None:
                pc_raw_path = (
                    fov_dir / f"{basename}_fov{fov:04d}_phase_contrast_raw.npy"
                )

            if not Path(pc_raw_path).exists():
                error_msg = f"Phase contrast raw file not found: {pc_raw_path}"
                raise FileNotFoundError(error_msg)

            # Create output file path
            binarized_path = fov_dir / f"{basename}_fov{fov:04d}_binarized.npy"

            # Load phase contrast data from NPY file
            logger.info(f"FOV {fov}: Loading phase contrast data...")
            phase_contrast_data = np.load(pc_raw_path, mmap_mode="r")

            # Derive dimensions from the loaded array and validate 3D shape
            if phase_contrast_data.ndim != 3:
                error_msg = f"Unexpected dims for phase contrast data: {phase_contrast_data.shape}"
                raise ValueError(error_msg)
            n_frames, height, width = (
                int(phase_contrast_data.shape[0]),
                int(phase_contrast_data.shape[1]),
                int(phase_contrast_data.shape[2]),
            )

            # Binarize using the selected algorithm
            status_msg = f"FOV {fov}: Applying segmentation..."
            logger.info(status_msg)

            # Single-seeded segmentation algorithm: log-std
            try:
                # Preallocate boolean output and call the single algorithm
                binarized_stack = np.zeros(phase_contrast_data.shape, dtype=bool)
                segment_cell(
                    phase_contrast_data,
                    binarized_stack,
                    progress_callback=partial(self.progress_callback, f=fov),
                )
            except InterruptedError:
                raise

            # Save segmentation results as NPY
            logger.info(f"FOV {fov}: Saving segmentation data...")
            np.save(binarized_path, binarized_stack)

            logger.info(f"FOV {fov} segmentation completed")

        except Exception as e:
            error_msg = f"Error processing FOV {fov} in segmentation: {str(e)}"
            logger.error(error_msg)
            raise
