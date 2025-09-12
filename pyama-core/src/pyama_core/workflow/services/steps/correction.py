"""
Correction processing service.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
from numpy.lib.format import open_memmap
import logging

from pyama_core.workflow.services.base import BaseProcessingService
from pyama_core.processing.background import correct_bg
from pyama_core.io.nikon import ND2Metadata
from pyama_core.workflow.workflow import ProcessingContext


logger = logging.getLogger(__name__)


class CorrectionService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Correction"

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
    ) -> None:
        base_name = metadata.base_name
        fov_dir = output_dir / f"fov_{fov:04d}"

        fl_raw_path = fov_dir / f"{base_name}_fov{fov:04d}_fluorescence_raw.npy"
        if not fl_raw_path.exists():
            logger.info(
                f"FOV {fov}: No fluorescence channel, skipping background correction"
            )
            return

        corrected_path = (
            fov_dir / f"{base_name}_fov{fov:04d}_fluorescence_corrected.npy"
        )

        segmentation_path = fov_dir / f"{base_name}_fov{fov:04d}_binarized.npy"
        if not segmentation_path.exists():
            raise FileNotFoundError(f"Segmentation data not found: {segmentation_path}")

        logger.info(f"FOV {fov}: Loading segmentation data...")
        segmentation_data = open_memmap(segmentation_path, mode="r")

        logger.info(f"FOV {fov}: Loading fluorescence data...")
        fluor_data = open_memmap(fl_raw_path, mode="r")

        if fluor_data.ndim != 3:
            raise ValueError(f"Unexpected fluorescence data dims: {fluor_data.shape}")
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

        corrected_memmap = None
        corrected_memmap = open_memmap(
            corrected_path,
            mode="w+",
            dtype=np.float32,
            shape=(n_frames, height, width),
        )

        def progress_callback(frame_idx, n_frames, message):
            fov_progress = int((frame_idx + 1) / n_frames * 100)
            progress_msg = f"FOV {fov}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"
            if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                logger.info(progress_msg)

        logger.info(f"FOV {fov}: Starting temporal background correction...")
        try:
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
