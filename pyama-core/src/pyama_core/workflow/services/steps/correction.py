"""
Correction processing service.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
from numpy.lib.format import open_memmap
import logging
from functools import partial

from pyama_core.workflow.services.base import BaseProcessingService
from pyama_core.processing.background import correct_bg
from pyama_core.io import ND2Metadata
from pyama_core.workflow.services.types import ProcessingContext


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

        npy_paths = context.setdefault("npy_paths", {})
        fov_paths = npy_paths.setdefault(
            fov, {"fluorescence": [], "fluorescence_corrected": []}
        )

        # Gather fluorescence tuples (ch_idx, path)
        fl_entries = fov_paths.get("fluorescence", []) or []
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
        bin_entry = fov_paths.get("seg")
        if isinstance(bin_entry, tuple) and len(bin_entry) == 2:
            seg_path = bin_entry[1]
        else:
            seg_path = fov_dir / f"{base_name}_fov{fov:04d}_seg.npy"
        if not Path(seg_path).exists():
            raise FileNotFoundError(f"Segmentation data not found: {seg_path}")
        logger.info(f"FOV {fov}: Loading segmentation data...")
        segmentation_data = open_memmap(seg_path, mode="r")

        fl_corrected_list = fov_paths.setdefault("fluorescence_corrected", [])

        for ch_idx, fl_raw_path in fl_entries:
            logger.info(f"FOV {fov}: Loading fluorescence data for channel {ch_idx}...")
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

            label_part = ""
            try:
                if 0 <= ch_idx < len(metadata.channel_names):
                    label_part = f"_{_sanitize(metadata.channel_names[ch_idx])}"
            except Exception:
                label_part = ""
            corrected_path = (
                fov_dir
                / f"{base_name}_fov{fov:04d}_fluorescence_c{ch_idx}{label_part}_corrected.npy"
            )

            corrected_memmap = open_memmap(
                corrected_path,
                mode="w+",
                dtype=np.float32,
                shape=(n_frames, height, width),
            )

            logger.info(
                f"FOV {fov}: Starting temporal background correction for channel {ch_idx}..."
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

            logger.info(f"FOV {fov}: Cleaning up channel {ch_idx}...")
            if corrected_memmap is not None:
                del corrected_memmap

            # Record output tuple
            try:
                fl_corrected_list.append((int(ch_idx), Path(corrected_path)))
            except Exception:
                pass

        logger.info(
            f"FOV {fov} background correction completed for {len(fl_entries)} channel(s)"
        )
