"""
Trace extraction processing service.
"""

from pathlib import Path
import numpy as np
from numpy.lib.format import open_memmap
import logging
from functools import partial

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.processing.extraction import extract_trace
from pyama_core.io import MicroscopyMetadata
from pyama_core.processing.workflow.services.types import (
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
            fl_entries = [(int(id), Path(p)) for id, p in fl_corr_entries]
        elif isinstance(fl_raw_entries, list) and fl_raw_entries:
            fl_entries = [(int(id), Path(p)) for id, p in fl_raw_entries]
        else:
            logger.info(
                f"FOV {fov}: No fluorescence stacks found; skipping fluorescence-specific features"
            )

        # Get feature selections from context
        channel_features = context.channels.fl_features if context.channels else {}
        pc_features = (
            list(context.channels.pc_features) if context.channels else []
        )

        def _compute_times(frame_count: int) -> np.ndarray:
            try:
                tp = getattr(metadata, "timepoints", None)
                if tp is not None and len(tp) == frame_count:
                    times_ms = np.asarray(tp, dtype=float)
                    return times_ms / 60000.0
            except Exception:
                pass
            return np.arange(frame_count, dtype=float)

        traces_list = fov_paths.traces_csv

        # Process phase contrast features if requested
        pc_entry = fov_paths.pc
        if pc_features:
            if not (isinstance(pc_entry, tuple) and len(pc_entry) == 2):
                logger.warning(
                    "Phase contrast features requested but no phase channel data available"
                )
            else:
                pc_channel = int(pc_entry[0])
                pc_path = Path(pc_entry[1])
                if not pc_path.exists():
                    logger.warning(
                        "Phase contrast features requested but file %s is missing",
                        pc_path,
                    )
                else:
                    pc_data = open_memmap(pc_path, mode="r")
                    pc_frames = int(pc_data.shape[0])
                    times = _compute_times(pc_frames)
                    unique_pc_features = sorted(dict.fromkeys(pc_features))
                    logger.info(
                        "FOV %d: Extracting phase features (%s) from channel %d",
                        fov,
                        ", ".join(unique_pc_features),
                        pc_channel,
                    )
                    try:
                        traces_df = extract_trace(
                            image=pc_data,
                            seg_labeled=seg_labeled,
                            times=times,
                            features=unique_pc_features,
                            progress_callback=partial(self.progress_callback, fov),
                        )
                    except InterruptedError:
                        raise InterruptedError("Phase feature extraction was interrupted")

                    traces_csv_path = (
                        fov_dir
                        / f"{base_name}_fov_{fov:03d}_traces_pc_ch_{pc_channel}.csv"
                    )
                    df_out = traces_df.copy()
                    df_out.insert(0, "fov", fov)
                    df_out.to_csv(traces_csv_path, index=False, float_format="%.6f")

                    try:
                        traces_list.append((pc_channel, Path(traces_csv_path)))
                    except Exception:
                        pass

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
            times = _compute_times(n_frames)

            logger.info(f"FOV {fov}: Starting feature extraction for ch {ch}...")
            configured_features = channel_features.get(ch, None)
            features_for_channel = (
                sorted(dict.fromkeys(configured_features))
                if configured_features
                else None
            )
            try:
                traces_df = extract_trace(
                    image=fl_data,
                    seg_labeled=seg_labeled,
                    times=times,
                    features=features_for_channel,  # Pass per-channel feature list
                    progress_callback=partial(self.progress_callback, fov),
                )
            except InterruptedError:
                raise InterruptedError("Feature extraction was interrupted")

            # We no longer rebuild a full (cell, time) grid here; we persist the
            # results exactly as returned by extract_trace.

            traces_csv_path = fov_dir / f"{base_name}_fov_{fov:03d}_traces_ch_{ch}.csv"
            # Write exactly what extract_trace returned; prepend 'fov' as the first column
            df_out = traces_df.copy()
            df_out.insert(0, "fov", fov)
            df_out.to_csv(traces_csv_path, index=False, float_format="%.6f")

            # Record output tuple
            try:
                traces_list.append((int(ch), Path(traces_csv_path)))
            except Exception:
                pass
