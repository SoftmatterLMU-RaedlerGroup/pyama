"""
Segmentation (formerly binarization) service.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
from functools import partial
import logging

from pyama_core.workflow.services.base import BaseProcessingService
from pyama_core.io.nikon import ND2Metadata
from pyama_core.processing.segmentation import segment_cell
from pyama_core.workflow.workflow import ProcessingContext


logger = logging.getLogger(__name__)


class SegmentationService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Segmentation"

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
    ) -> None:
        basename = metadata.base_name
        fov_dir = output_dir / f"fov_{fov:04d}"

        pc_raw_path = None
        try:
            pc_raw_path = (
                context.get("npy_paths", {}).get(fov, {}).get("phase_contrast")
            )
        except Exception:
            pc_raw_path = None

        if pc_raw_path is None:
            pc_raw_path = fov_dir / f"{basename}_fov{fov:04d}_phase_contrast_raw.npy"

        if not Path(pc_raw_path).exists():
            error_msg = f"Phase contrast raw file not found: {pc_raw_path}"
            raise FileNotFoundError(error_msg)

        binarized_path = fov_dir / f"{basename}_fov{fov:04d}_binarized.npy"

        logger.info(f"FOV {fov}: Loading phase contrast data...")
        phase_contrast_data = np.load(pc_raw_path, mmap_mode="r")

        if phase_contrast_data.ndim != 3:
            error_msg = (
                f"Unexpected dims for phase contrast data: {phase_contrast_data.shape}"
            )
            raise ValueError(error_msg)

        logger.info(f"FOV {fov}: Applying segmentation...")
        try:
            binarized_stack = np.zeros(phase_contrast_data.shape, dtype=bool)
            segment_cell(
                phase_contrast_data,
                binarized_stack,
                progress_callback=partial(self.progress_callback, f=fov),
            )
        except InterruptedError:
            raise

        logger.info(f"FOV {fov}: Saving segmentation data...")
        np.save(binarized_path, binarized_stack)

        logger.info(f"FOV {fov} segmentation completed")
