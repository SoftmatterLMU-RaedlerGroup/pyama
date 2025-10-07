"""
Correction processing service.
"""

from pathlib import Path
import numpy as np
from numpy.lib.format import open_memmap
import logging
from functools import partial

from ..base import BaseProcessingService
from pyama_core.processing.background import correct_bg
from pyama_core.io import MicroscopyMetadata
from ..types import (
    ProcessingContext,
    ensure_context,
    ensure_results_paths_entry,
)


logger = logging.getLogger(__name__)


class CorrectionService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Correction"

    def process_fov(
        self,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
    ) -> None:
        context = ensure_context(context)
        base_name = metadata.base_name
        fov_dir = output_dir / f"fov_{fov:03d}"

        if context.results_paths is None:
            context.results_paths = {}
        fov_paths = context.results_paths.setdefault(fov, ensure_results_paths_entry())

        # Gather fluorescence tuples (ch, path)
        fl_entries = fov_paths.fl
        if not isinstance(fl_entries, list):
            fl_entries = []
        if not fl_entries:
            logger.info(f"FOV {fov}: No fluorescence channels, skipping correction")
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
        bin_entry = fov_paths.seg
        if isinstance(bin_entry, tuple) and len(bin_entry) == 2:
            seg_path = bin_entry[1]
        else:
            # Fallback if context missing path
            seg_path = fov_dir / f"{base_name}_fov_{fov:03d}_seg_ch_0.npy"
        if not Path(seg_path).exists():
            raise FileNotFoundError(f"Segmentation data not found: {seg_path}")
        logger.info(f"FOV {fov}: Loading segmentation data...")
        segmentation_data = open_memmap(seg_path, mode="r")

        fl_corrected_list = fov_paths.fl_corrected

        for ch, fl_raw_path in fl_entries:
            corrected_path = (
                fov_dir / f"{base_name}_fov_{fov:03d}_fl_corrected_ch_{ch}.npy"
            )
            # If output exists, record and skip this channel
            if Path(corrected_path).exists():
                logger.info(
                    f"FOV {fov}: Corrected fluorescence for ch {ch} already exists, skipping"
                )
                try:
                    fl_corrected_list.append((int(ch), Path(corrected_path)))
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

            corrected_memmap = open_memmap(
                corrected_path,
                mode="w+",
                dtype=np.float32,
                shape=(n_frames, height, width),
            )

            logger.info(
                f"FOV {fov}: Starting temporal background correction for channel {ch}..."
            )
            try:
                correct_bg(
                    fluor_data.astype(np.float32),
                    segmentation_data,
                    corrected_memmap,
                    progress_callback=partial(self.progress_callback, fov),
                )
            except InterruptedError:
                if corrected_memmap is not None:
                    del corrected_memmap
                raise

            logger.info(f"FOV {fov}: Cleaning up channel {ch}...")
            if corrected_memmap is not None:
                del corrected_memmap

            # Record output tuple
            try:
                fl_corrected_list.append((int(ch), Path(corrected_path)))
            except Exception:
                pass

        logger.info(
            f"FOV {fov} background correction completed for {len(fl_entries)} channel(s)"
        )
