"""
Cell tracking processing service.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import logging

from pyama_core.workflow.services.base import BaseProcessingService
from pyama_core.processing.tracking import track_cell
from pyama_core.io import ND2Metadata
from pyama_core.workflow import ProcessingContext


logger = logging.getLogger(__name__)


class TrackingService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Tracking"

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
    ) -> None:
        base_name = metadata.base_name
        fov_dir = output_dir / f"fov_{fov:04d}"

        segmentation_path = fov_dir / f"{base_name}_fov{fov:04d}_binarized.npy"
        if not segmentation_path.exists():
            raise FileNotFoundError(
                f"Binary segmentation data not found: {segmentation_path}"
            )

        segmentation_data = np.load(segmentation_path, mmap_mode="r")
        n_frames, height, width = segmentation_data.shape
        seg_labeled = np.zeros((n_frames, height, width), dtype=np.uint16)

        def progress_callback(frame_idx, n_frames, message):
            fov_progress = int((frame_idx + 1) / n_frames * 100)
            progress_msg = f"FOV {fov}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"
            if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                logger.info(progress_msg)

        logger.info(f"FOV {fov}: Starting cell tracking...")
        try:
            track_cell(
                image=segmentation_data,
                out=seg_labeled,
                progress_callback=progress_callback,
            )
        except InterruptedError:
            raise

        seg_labeled_path = fov_dir / f"{base_name}_fov{fov:04d}_seg_labeled.npy"
        np.save(seg_labeled_path, seg_labeled)

        logger.info(f"FOV {fov} cell tracking completed")
