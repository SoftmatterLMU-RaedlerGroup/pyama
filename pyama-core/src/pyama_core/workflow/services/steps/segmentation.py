"""
Segmentation (formerly binarization) service.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
from functools import partial
import logging

from pyama_core.workflow.services.base import BaseProcessingService
from pyama_core.io import ND2Metadata
from pyama_core.processing.segmentation import segment_cell
from pyama_core.workflow.services.types import ProcessingContext
from numpy.lib.format import open_memmap


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

        npy_paths = context.setdefault("npy_paths", {})
        fov_paths = npy_paths.setdefault(
            fov, {"fluorescence": [], "fluorescence_corrected": []}
        )

        # phase_contrast may be a tuple (channel_idx, path) or legacy Path
        pc_entry = fov_paths.get("phase_contrast")
        pc_idx = None
        pc_raw_path = None
        if isinstance(pc_entry, tuple) and len(pc_entry) == 2:
            pc_idx, pc_raw_path = int(pc_entry[0]), pc_entry[1]
        else:
            pc_raw_path = pc_entry
        if pc_raw_path is None:
            pc_raw_path = fov_dir / f"{basename}_fov{fov:04d}_phase_contrast_raw.npy"

        if not Path(pc_raw_path).exists():
            error_msg = f"Phase contrast raw file not found: {pc_raw_path}"
            raise FileNotFoundError(error_msg)

        # Name binarized output, include pc channel index/label if available
        def _sanitize(name: str) -> str:
            try:
                safe = "".join(
                    c if c.isalnum() or c in ("-", "_") else "_" for c in name
                )
                while "__" in safe:
                    safe = safe.replace("__", "_")
                return safe.strip("_") or "unnamed"
            except Exception:
                return "unnamed"

        label_part = ""
        try:
            if pc_idx is not None and 0 <= pc_idx < len(metadata.channel_names):
                label_part = f"_{_sanitize(metadata.channel_names[pc_idx])}"
        except Exception:
            label_part = ""

        seg_entry = fov_paths.get("seg")
        if isinstance(seg_entry, tuple) and len(seg_entry) == 2:
            seg_path = seg_entry[1]
        else:
            suffix = f"_pc_c{pc_idx}{label_part}" if pc_idx is not None else ""
            seg_path = fov_dir / f"{basename}_fov{fov:04d}_seg{suffix}.npy"

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
        # Record output as a tuple (pc_idx, path) if idx known
        try:
            if pc_idx is None:
                fov_paths["seg"] = (0, Path(seg_path))
            else:
                fov_paths["seg"] = (int(pc_idx), Path(seg_path))
        except Exception:
            pass

        logger.info(f"FOV {fov} segmentation completed")
