"""
Segmentation (formerly binarization) service.
"""

from pathlib import Path
import numpy as np
from functools import partial
import logging

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.io import MicroscopyMetadata
from pyama_core.processing.segmentation import segment_cell
from pyama_core.processing.workflow.services.types import (
    ProcessingContext,
    ensure_context,
    ensure_results_paths_entry,
)
from numpy.lib.format import open_memmap


logger = logging.getLogger(__name__)


class SegmentationService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Segmentation"

    def process_fov(
        self,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
    ) -> None:
        context = ensure_context(context)
        basename = metadata.base_name
        fov_dir = output_dir / f"fov_{fov:03d}"

        if context.results_paths is None:
            context.results_paths = {}
        fov_paths = context.results_paths.setdefault(fov, ensure_results_paths_entry())

        # pc may be a tuple (channel_id, path) or legacy Path
        pc_entry = fov_paths.pc
        pc_id = None
        pc_raw_path = None
        if isinstance(pc_entry, tuple) and len(pc_entry) == 2:
            pc_id, pc_raw_path = int(pc_entry[0]), pc_entry[1]
        else:
            pc_raw_path = pc_entry
        if pc_raw_path is None:
            # Fallback to simplified naming if context missing path
            assumed_id = 0 if pc_id is None else pc_id
            pc_raw_path = fov_dir / f"{basename}_fov_{fov:03d}_pc_ch_{assumed_id}.npy"

        if not Path(pc_raw_path).exists():
            error_msg = f"Phase contrast file not found: {pc_raw_path}"
            raise FileNotFoundError(error_msg)

        # Build simplified seg filename
        seg_entry = fov_paths.seg
        if isinstance(seg_entry, tuple) and len(seg_entry) == 2:
            seg_path = seg_entry[1]
        else:
            assumed_id = 0 if pc_id is None else pc_id
            seg_path = fov_dir / f"{basename}_fov_{fov:03d}_seg_ch_{assumed_id}.npy"

        # If output already exists, record and skip
        if Path(seg_path).exists():
            logger.info(f"FOV {fov}: Segmentation already exists, skipping")
            try:
                if pc_id is None:
                    fov_paths.seg = (0, Path(seg_path))
                else:
                    fov_paths.seg = (int(pc_id), Path(seg_path))
            except Exception:
                pass
            return

        logger.info(f"FOV {fov}: Loading phase contrast data...")
        phase_contrast_data = np.load(pc_raw_path, mmap_mode="r")

        if phase_contrast_data.ndim != 3:
            error_msg = (
                f"Unexpected dims for phase contrast data: {phase_contrast_data.shape}"
            )
            raise ValueError(error_msg)

        logger.info(f"FOV {fov}: Applying segmentation...")
        seg_memmap = None
        try:
            seg_memmap = open_memmap(
                seg_path, mode="w+", dtype=bool, shape=phase_contrast_data.shape
            )
            segment_cell(
                phase_contrast_data,
                seg_memmap,
                progress_callback=partial(self.progress_callback, fov),
            )
        except InterruptedError:
            if seg_memmap is not None:
                try:
                    del seg_memmap
                except Exception:
                    pass
            raise
        finally:
            if seg_memmap is not None:
                try:
                    del seg_memmap
                except Exception:
                    pass
        # Record output as a tuple (pc_id, path) if id known
        try:
            if pc_id is None:
                fov_paths.seg = (0, Path(seg_path))
            else:
                fov_paths.seg = (int(pc_id), Path(seg_path))
        except Exception:
            pass

        logger.info(f"FOV {fov} segmentation completed")
