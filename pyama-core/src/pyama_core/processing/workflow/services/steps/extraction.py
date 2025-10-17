"""
Trace extraction processing service.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from numpy.lib.format import open_memmap
import logging
from functools import partial

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.processing.extraction import extract_trace
from pyama_core.io import MicroscopyMetadata
from pyama_core.processing.workflow.services.types import (
    ProcessingContext,
    ensure_context,
    ensure_results_entry,
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

        if context.results is None:
            context.results = {}
        fov_paths = context.results.setdefault(fov, ensure_results_entry())

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

        traces_output_path = (
            fov_dir / f"{base_name}_fov_{fov:03d}_traces.csv"
        )
        if traces_output_path.exists():
            logger.info(
                "FOV %d: Combined traces CSV already exists, skipping extraction", fov
            )
            fov_paths.traces = traces_output_path
            return

        channel_frames: list[tuple[int, pd.DataFrame]] = []

        # Determine fluorescence sources: prefer corrected tuples, fallback to raw tuples
        fl_corr_entries = fov_paths.fl_corrected
        fl_raw_entries = fov_paths.fl
        fl_entries: list[tuple[int, Path]] = []
        if isinstance(fl_corr_entries, list) and fl_corr_entries:
            fl_entries = [(int(id), Path(p)) for id, p in fl_corr_entries]
        elif isinstance(fl_raw_entries, list) and fl_raw_entries:
            fl_entries = [(int(id), Path(p)) for id, p in fl_raw_entries]

        # Get feature selections from context
        channel_features: dict[int, list[str]] = {}
        pc_features: list[str] = []
        if context.channels:
            channel_features = context.channels.get_fl_feature_map()
            pc_features = context.channels.get_pc_features()

        def _compute_times(frame_count: int) -> np.ndarray:
            try:
                tp = getattr(metadata, "timepoints", None)
                if tp is not None and len(tp) == frame_count:
                    times_ms = np.asarray(tp, dtype=float)
                    return times_ms / 60000.0
            except Exception:
                pass
            return np.arange(frame_count, dtype=float)

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
                        channel_frames.append((pc_channel, traces_df))
                    except InterruptedError:
                        raise InterruptedError("Phase feature extraction was interrupted")
                    finally:
                        try:
                            del pc_data
                        except Exception:
                            pass

        if not fl_entries:
            logger.info(
                "FOV %d: No fluorescence stacks found; skipping fluorescence-specific features",
                fov,
            )

        for ch, fl_path in fl_entries:
            if fl_path is None or not Path(fl_path).exists():
                logger.info(f"FOV {fov}: Fluorescence channel {ch} not found, skipping")
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
                    features=features_for_channel,
                    progress_callback=partial(self.progress_callback, fov),
                )
                channel_frames.append((int(ch), traces_df))
            except InterruptedError:
                raise InterruptedError("Feature extraction was interrupted")
            finally:
                try:
                    del fl_data
                except Exception:
                    pass

        if not channel_frames:
            logger.info("FOV %d: No trace data produced; skipping CSV generation", fov)
            return

        BASE_COLUMNS = ["cell", "frame", "time", "good", "position_x", "position_y"]
        merged_df: pd.DataFrame | None = None

        for channel_id, df in channel_frames:
            if df.empty:
                continue
            feature_cols = [col for col in df.columns if col not in BASE_COLUMNS]
            rename_map = {
                col: f"{col}_ch_{channel_id}" for col in feature_cols
            }
            prepared = df[BASE_COLUMNS + feature_cols].rename(columns=rename_map)
            if merged_df is None:
                merged_df = prepared
            else:
                merged_df = merged_df.merge(
                    prepared,
                    on=BASE_COLUMNS,
                    how="outer",
                )

        if merged_df is None or merged_df.empty:
            logger.info("FOV %d: Combined trace DataFrame is empty; skipping output", fov)
            return

        merged_df.sort_values(["cell", "frame", "time"], inplace=True)
        merged_df.insert(0, "fov", fov)
        merged_df.to_csv(traces_output_path, index=False, float_format="%.6f")

        fov_paths.traces = traces_output_path
