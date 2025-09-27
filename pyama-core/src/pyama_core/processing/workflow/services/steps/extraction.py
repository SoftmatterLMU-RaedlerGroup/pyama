"""
Trace extraction processing service.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
from numpy.lib.format import open_memmap
import logging
from functools import partial

from ..base import BaseProcessingService
from pyama_core.processing.extraction import extract_trace
from pyama_core.io import MicroscopyMetadata
from ..types import (
    ProcessingContext,
    ensure_context,
    ensure_results_paths_entry,
)


logger = logging.getLogger(__name__)


class ExtractionService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Extraction"

    def process_fov(
        self,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
    ) -> None:
        context = ensure_context(context)
        base_name = metadata.base_name

        logger.info(f"FOV {fov}: Loading input data...")
        fov_dir = output_dir / f"fov_{fov:03d}"

        if context.results_paths is None:
            context.results_paths = {}
        fov_paths = context.results_paths.setdefault(fov, ensure_results_paths_entry())

        seg_entry = fov_paths.seg_labeled
        if isinstance(seg_entry, tuple) and len(seg_entry) == 2:
            seg_labeled_path = seg_entry[1]
        else:
            seg_labeled_path = fov_dir / f"{base_name}_fov{fov:03d}_seg_labeled.npy"
        if not seg_labeled_path.exists():
            raise FileNotFoundError(
                f"Tracked segmentation data not found: {seg_labeled_path}"
            )
        seg_labeled = open_memmap(seg_labeled_path, mode="r")

        # Determine fluorescence sources: prefer corrected tuples, fallback to raw tuples
        fl_corr_entries = fov_paths.fl_corrected
        fl_raw_entries = fov_paths.fl
        fl_entries: list[tuple[int, Path]] = []
        if isinstance(fl_corr_entries, list) and fl_corr_entries:
            fl_entries = [(int(idx), Path(p)) for idx, p in fl_corr_entries]
        elif isinstance(fl_raw_entries, list) and fl_raw_entries:
            fl_entries = [(int(idx), Path(p)) for idx, p in fl_raw_entries]
        else:
            logger.info(
                f"FOV {fov}: No fluorescence data found, skipping trace extraction"
            )
            return

        traces_list = fov_paths.traces_csv

        for ch, fl_path in fl_entries:
            if fl_path is None or not Path(fl_path).exists():
                logger.info(f"FOV {fov}: Fluorescence channel {ch} not found, skipping")
                continue

            traces_csv_path = fov_dir / f"{base_name}_fov_{fov:03d}_traces_ch_{ch}.csv"
            # If output exists, record and skip this channel
            if Path(traces_csv_path).exists():
                logger.info(
                    f"FOV {fov}: Traces CSV for ch {ch} already exists, skipping"
                )
                try:
                    traces_list.append((int(ch), Path(traces_csv_path)))
                except Exception:
                    pass
                continue

            fl_data = open_memmap(fl_path, mode="r")

            n_frames = int(fl_data.shape[0])
            # Prefer real acquisition times from metadata when available
            try:
                tp = getattr(metadata, "timepoints", None)
                if tp is not None and len(tp) == n_frames:
                    # Convert timepoints to minutes (assumes metadata provides ms)
                    times_ms = np.asarray(tp, dtype=float)
                    times = times_ms / 60000.0
                else:
                    # Fallback: frame index in minutes assuming 1 frame per minute
                    times = np.arange(n_frames, dtype=float)
            except Exception:
                # Fallback: frame index
                times = np.arange(n_frames, dtype=float)

            logger.info(f"FOV {fov}: Starting feature extraction for ch {ch}...")
            try:
                traces_df = extract_trace(
                    image=fl_data,
                    seg_labeled=seg_labeled,
                    times=times,
                    progress_callback=partial(self.progress_callback, fov),
                )
            except InterruptedError:
                raise InterruptedError("Feature extraction was interrupted")

            # We no longer rebuild a full (cell, time) grid here; we persist the
            # results exactly as returned by extract_trace.

            traces_csv_path = fov_dir / f"{base_name}_fov_{fov:03d}_traces_ch_{ch}.csv"
            # Write exactly what extract_trace returned; prepend 'fov' as the first column
            df_out = traces_df.reset_index()
            df_out.insert(0, "fov", fov)
            df_out.to_csv(traces_csv_path, index=False, float_format="%.6f")

            # Record output tuple
            try:
                traces_list.append((int(ch), Path(traces_csv_path)))
            except Exception:
                pass
