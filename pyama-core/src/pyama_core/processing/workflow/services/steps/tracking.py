"""
Cell tracking processing service.
"""

from pathlib import Path
import numpy as np
import logging
from functools import partial

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.processing.tracking import track_cell
from pyama_core.io import MicroscopyMetadata
from pyama_core.types.processing import (
    ProcessingContext,
    ensure_context,
    ensure_results_entry,
)
from numpy.lib.format import open_memmap


logger = logging.getLogger(__name__)


class TrackingService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Tracking"

    def process_fov(
        self,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
        cancel_event=None,
    ) -> None:
        context = ensure_context(context)
        base_name = metadata.base_name
        fov_dir = output_dir / f"fov_{fov:03d}"

        if context.results is None:
            context.results = {}
        fov_paths = context.results.setdefault(fov, ensure_results_entry())

        # seg is a tuple (pc_id, path) or legacy path
        bin_entry = fov_paths.seg
        if isinstance(bin_entry, tuple) and len(bin_entry) == 2:
            pc_id, segmentation_path = int(bin_entry[0]), bin_entry[1]
        else:
            segmentation_path = bin_entry
        if segmentation_path is None:
            ch = pc_id if "pc_id" in locals() and pc_id is not None else 0
            segmentation_path = fov_dir / f"{base_name}_fov_{fov:03d}_seg_ch_{ch}.npy"
        if not Path(segmentation_path).exists():
            raise FileNotFoundError(f"Segmentation data not found: {segmentation_path}")

        segmentation_data = np.load(segmentation_path, mmap_mode="r")
        n_frames, height, width = segmentation_data.shape

        # Build simplified labeled seg filename
        seg_labeled_entry = fov_paths.seg_labeled
        if isinstance(seg_labeled_entry, tuple) and len(seg_labeled_entry) == 2:
            seg_labeled_path = seg_labeled_entry[1]
        else:
            ch = pc_id if "pc_id" in locals() and pc_id is not None else 0
            seg_labeled_path = (
                fov_dir / f"{base_name}_fov_{fov:03d}_seg_labeled_ch_{ch}.npy"
            )

        # If output already exists, record and skip
        if Path(seg_labeled_path).exists():
            logger.info("FOV %d: Tracked segmentation already exists, skipping", fov)
            try:
                if "pc_id" in locals() and pc_id is not None:
                    fov_paths.seg_labeled = (int(pc_id), Path(seg_labeled_path))
                else:
                    fov_paths.seg_labeled = (0, Path(seg_labeled_path))
            except Exception:
                pass
            return

        logger.info("FOV %d: Starting cell tracking...", fov)
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
                cancel_event=cancel_event,
            )
            # Flush changes to disk
            seg_labeled_memmap.flush()
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
            if "pc_id" in locals() and pc_id is not None:
                fov_paths.seg_labeled = (int(pc_id), Path(seg_labeled_path))
            else:
                fov_paths.seg_labeled = (0, Path(seg_labeled_path))
        except Exception:
            pass
        try:
            if "pc_id" in locals() and pc_id is not None:
                fov_paths.seg_labeled = (int(pc_id), Path(seg_labeled_path))
            else:
                fov_paths.seg_labeled = (0, Path(seg_labeled_path))
        except Exception:
            pass

        logger.info("FOV %d: Cell tracking completed", fov)
