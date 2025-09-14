"""
Cell tracking processing service.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import logging
from functools import partial

from pyama_core.workflow.services.base import BaseProcessingService
from pyama_core.processing.tracking import track_cell
from pyama_core.io import ND2Metadata
from pyama_core.workflow.services.types import ProcessingContext
from numpy.lib.format import open_memmap


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

        npy_paths = context.setdefault("npy_paths", {})
        fov_paths = npy_paths.setdefault(
            fov, {"fl": [], "fl_corrected": []}
        )

        # seg is a tuple (pc_idx, path) or legacy path
        bin_entry = fov_paths.get("seg")
        if isinstance(bin_entry, tuple) and len(bin_entry) == 2:
            pc_idx, segmentation_path = int(bin_entry[0]), bin_entry[1]
        else:
            segmentation_path = bin_entry
        if segmentation_path is None:
            ch = pc_idx if "pc_idx" in locals() and pc_idx is not None else 0
            segmentation_path = fov_dir / f"{base_name}_fov_{fov:04d}_seg_ch_{ch}.npy"
        if not Path(segmentation_path).exists():
            raise FileNotFoundError(f"Segmentation data not found: {segmentation_path}")

        segmentation_data = np.load(segmentation_path, mmap_mode="r")
        n_frames, height, width = segmentation_data.shape

        # Build simplified labeled seg filename
        seg_labeled_entry = fov_paths.get("seg_labeled")
        if isinstance(seg_labeled_entry, tuple) and len(seg_labeled_entry) == 2:
            seg_labeled_path = seg_labeled_entry[1]
        else:
            ch = pc_idx if "pc_idx" in locals() and pc_idx is not None else 0
            seg_labeled_path = fov_dir / f"{base_name}_fov_{fov:04d}_seg_labeled_ch_{ch}.npy"

        # If output already exists, record and skip
        if Path(seg_labeled_path).exists():
            logger.info(f"FOV {fov}: Tracked segmentation already exists, skipping")
            try:
                if "pc_idx" in locals() and pc_idx is not None:
                    fov_paths["seg_labeled"] = (int(pc_idx), Path(seg_labeled_path))
                else:
                    fov_paths["seg_labeled"] = (0, Path(seg_labeled_path))
            except Exception:
                pass
            return

        logger.info(f"FOV {fov}: Starting cell tracking...")
        seg_labeled_memmap = None
        try:
            seg_labeled_memmap = open_memmap(
                seg_labeled_path,
                mode="w+",
                dtype=np.uint16,
                shape=(n_frames, height, width),
            )
            track_cell(
                image=segmentation_data,
                out=seg_labeled_memmap,
                progress_callback=partial(self.progress_callback, fov),
            )
        except InterruptedError:
            if seg_labeled_memmap is not None:
                try:
                    del seg_labeled_memmap
                except Exception:
                    pass
            raise
        finally:
            if seg_labeled_memmap is not None:
                try:
                    del seg_labeled_memmap
                except Exception:
                    pass
        # Record output path into context
        try:
            if "pc_idx" in locals() and pc_idx is not None:
                fov_paths["seg_labeled"] = (int(pc_idx), Path(seg_labeled_path))
            else:
                fov_paths["seg_labeled"] = (0, Path(seg_labeled_path))
        except Exception:
            pass

        logger.info(f"FOV {fov} cell tracking completed")
