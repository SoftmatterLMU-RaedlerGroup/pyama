"""
Background estimation processing service.

This service estimates background fluorescence using tiled interpolation.
The estimated background is saved for later correction processing.
"""

from pathlib import Path
import numpy as np
from numpy.lib.format import open_memmap
import logging
from functools import partial

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.processing.background import estimate_background
from pyama_core.io import MicroscopyMetadata
from pyama_core.processing.workflow.services.types import (
    ProcessingContext,
    ensure_context,
    ensure_results_entry,
)


logger = logging.getLogger(__name__)


class BackgroundEstimationService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Background Estimation"

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

        context_results = context.setdefault("results", {})
        fov_paths = context_results.setdefault(fov, ensure_results_entry())

        # Gather fluorescence tuples (ch, path)
        fl_entries = fov_paths.get("fl", [])
        if not isinstance(fl_entries, list):
            fl_entries = []
        if not fl_entries:
            logger.info(f"FOV {fov}: No fluorescence channels, skipping background estimation")
            return

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

        # Load segmentation once
        bin_entry = fov_paths.get("seg")
        if isinstance(bin_entry, tuple) and len(bin_entry) == 2:
            seg_path = Path(bin_entry[1])
        else:
            # Fallback if context missing path
            seg_path = fov_dir / f"{base_name}_fov_{fov:03d}_seg_ch_0.npy"
        if not seg_path.exists():
            raise FileNotFoundError(f"Segmentation data not found: {seg_path}")
        logger.info(f"FOV {fov}: Loading segmentation data...")
        segmentation_data = open_memmap(seg_path, mode="r")

        fl_background_list = fov_paths.get("fl_background", [])

        for ch, fl_raw_path_str in fl_entries:
            fl_raw_path = Path(fl_raw_path_str)
            background_path = (
                fov_dir / f"{base_name}_fov_{fov:03d}_fl_background_ch_{ch}.npy"
            )
            # If output exists, record and skip this channel
            if Path(background_path).exists():
                logger.info(
                    f"FOV {fov}: Background interpolation for ch {ch} already exists, skipping"
                )
                try:
                    fl_background_list.append((int(ch), str(background_path)))
                except Exception:
                    pass
                continue

            logger.info(f"FOV {fov}: Loading fluorescence data for channel {ch}...")
            fluor_data = open_memmap(fl_raw_path, mode="r")

            if fluor_data.ndim != 3:
                raise ValueError(
                    f"Unexpected fluorescence data dims: {fluor_data.shape}"
                )
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

            background_memmap = open_memmap(
                background_path,
                mode="w+",
                dtype=np.float32,
                shape=(n_frames, height, width),
            )

            logger.info(
                f"FOV {fov}: Starting background estimation for channel {ch}..."
            )
            try:
                estimate_background(
                    fluor_data.astype(np.float32),
                    segmentation_data,
                    background_memmap,
                    progress_callback=partial(self.progress_callback, fov),
                    cancel_event=cancel_event,
                )
                # Flush changes to disk
                background_memmap.flush()
            except InterruptedError:
                if background_memmap is not None:
                    del background_memmap
                raise

            logger.info(f"FOV {fov}: Cleaning up channel {ch}...")
            if background_memmap is not None:
                del background_memmap

            # Record output tuple
            try:
                fl_background_list.append((int(ch), str(background_path)))
            except Exception:
                pass

        # Update fov_paths with the fl_background list
        fov_paths["fl_background"] = fl_background_list

        logger.info(
            f"FOV {fov} background estimation completed for {len(fl_entries)} channel(s)"
        )
