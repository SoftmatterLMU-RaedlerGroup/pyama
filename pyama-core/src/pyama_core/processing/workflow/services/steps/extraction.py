"""
Trace extraction processing service.
"""

import logging
from dataclasses import fields as dataclass_fields
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.format import open_memmap

from pyama_core.io import MicroscopyMetadata
from pyama_core.processing.extraction import extract_trace
from pyama_core.processing.extraction.run import Result
from pyama_core.processing.workflow.services.base import BaseProcessingService
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
        cancel_event=None,
    ) -> None:
        context = ensure_context(context)
        base_name = metadata.base_name

        # Get background weight from params (default: 0.0)
        background_weight = 0.0
        erosion_size = 0
        if context.params:
            background_weight = context.params.get("background_weight", 0.0)
            try:
                background_weight = float(background_weight)
                # Clamp background_weight between 0 and 1
                if background_weight < 0.0:
                    logger.warning(
                        f"background_weight {background_weight} is less than 0, clamping to 0.0"
                    )
                    background_weight = 0.0
                elif background_weight > 1.0:
                    logger.warning(
                        f"background_weight {background_weight} is greater than 1, clamping to 1.0"
                    )
                    background_weight = 1.0
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid background_weight in params: {context.params.get('background_weight')}, using default 0.0"
                )
                background_weight = 0.0

            # Get erosion_size from params (default: 0)
            erosion_size = context.params.get("erosion_size", 0)
            try:
                erosion_size = int(erosion_size)
                if erosion_size < 0:
                    logger.warning(
                        f"erosion_size {erosion_size} is less than 0, clamping to 0"
                    )
                    erosion_size = 0
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid erosion_size in params: {context.params.get('erosion_size')}, using default 0"
                )
                erosion_size = 0

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

        try:
            traces_output_path = fov_dir / f"{base_name}_fov_{fov:03d}_traces.csv"
            if traces_output_path.exists():
                logger.info(
                    "FOV %d: Combined traces CSV already exists, skipping extraction",
                    fov,
                )
                fov_paths.traces = traces_output_path
                return

            channel_frames: list[tuple[int, pd.DataFrame]] = []

            # Build mappings for raw and background fluorescence data
            fl_background_entries = fov_paths.fl_background
            fl_raw_entries = fov_paths.fl
            
            # Create dictionaries mapping channel ID to path
            fl_raw_map: dict[int, Path] = {}
            if isinstance(fl_raw_entries, list):
                fl_raw_map = {int(id): Path(p) for id, p in fl_raw_entries}
            
            fl_background_map: dict[int, Path] = {}
            if isinstance(fl_background_entries, list):
                fl_background_map = {int(id): Path(p) for id, p in fl_background_entries}
            
            # Determine which channels to process (union of raw and background channels)
            channels_to_process = set(fl_raw_map.keys()) | set(fl_background_map.keys())

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

            # Check for cancellation before processing phase contrast features
            if cancel_event and cancel_event.is_set():
                logger.info(
                    f"Extraction cancelled before phase contrast processing for FOV {fov}"
                )
                return

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
                        try:
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
                                # PC features don't use background correction - pass zeros
                                pc_background = np.zeros_like(pc_data, dtype=np.float32)
                                traces_df = extract_trace(
                                    image=pc_data,
                                    seg_labeled=seg_labeled,
                                    times=times,
                                    background=pc_background,
                                    features=unique_pc_features,
                                    progress_callback=partial(
                                        self.progress_callback, fov
                                    ),
                                    cancel_event=cancel_event,
                                    background_weight=background_weight,
                                    erosion_size=erosion_size,
                                )
                                channel_frames.append((pc_channel, traces_df))
                            except InterruptedError:
                                raise InterruptedError(
                                    "Phase feature extraction was interrupted"
                                )
                        finally:
                            try:
                                del pc_data
                            except Exception:
                                pass

            if not channels_to_process:
                logger.info(
                    "FOV %d: No fluorescence stacks found; skipping fluorescence-specific features",
                    fov,
                )

            for ch in sorted(channels_to_process):
                # Check for cancellation before processing each fluorescence channel
                if cancel_event and cancel_event.is_set():
                    logger.info(
                        f"Extraction cancelled at fluorescence channel {ch} for FOV {fov}"
                    )
                    return

                # Load raw fluorescence data
                fl_raw_path = fl_raw_map.get(ch)
                if fl_raw_path is None or not fl_raw_path.exists():
                    logger.warning(
                        f"FOV {fov}: Raw fluorescence channel {ch} not found, skipping"
                    )
                    continue

                fl_raw_data = open_memmap(fl_raw_path, mode="r")
                
                # Load background data if available
                fl_background_path = fl_background_map.get(ch)
                fl_background_data = None
                if fl_background_path is not None and fl_background_path.exists():
                    fl_background_data = open_memmap(fl_background_path, mode="r")
                    # Verify shapes match
                    if fl_raw_data.shape != fl_background_data.shape:
                        logger.warning(
                            f"FOV {fov}: Shape mismatch between raw and background for channel {ch}, "
                            f"using raw data only"
                        )
                        try:
                            del fl_background_data
                        except Exception:
                            pass
                        fl_background_data = None

                try:
                    n_frames = int(fl_raw_data.shape[0])
                    times = _compute_times(n_frames)

                    configured_features = channel_features.get(ch, None)
                    features_for_channel = (
                        sorted(dict.fromkeys(configured_features))
                        if configured_features
                        else None
                    )
                    
                    # Always provide background (zeros if not available)
                    if fl_background_data is not None:
                        background_for_extraction = fl_background_data.astype(np.float32)
                        logger.info(
                            "FOV %d: Extracting fluorescence features (%s) from channel %d "
                            "(background data available for correction)",
                            fov,
                            ", ".join(features_for_channel)
                            if features_for_channel
                            else "none",
                            ch,
                        )
                    else:
                        # Create zeros array matching raw data shape
                        background_for_extraction = np.zeros_like(fl_raw_data, dtype=np.float32)
                        logger.info(
                            "FOV %d: Extracting fluorescence features (%s) from channel %d",
                            fov,
                            ", ".join(features_for_channel)
                            if features_for_channel
                            else "none",
                            ch,
                        )
                    
                    try:
                        traces_df = extract_trace(
                            image=fl_raw_data.astype(np.float32),
                            seg_labeled=seg_labeled,
                            times=times,
                            background=background_for_extraction,
                            features=features_for_channel,
                            progress_callback=partial(self.progress_callback, fov),
                            cancel_event=cancel_event,
                            background_weight=background_weight,
                            erosion_size=erosion_size,
                        )
                        channel_frames.append((int(ch), traces_df))
                    except InterruptedError:
                        raise InterruptedError("Feature extraction was interrupted")
                finally:
                    try:
                        del fl_raw_data
                    except Exception:
                        pass
                    if fl_background_data is not None:
                        try:
                            del fl_background_data
                        except Exception:
                            pass

            base_cols = [f.name for f in dataclass_fields(Result)]
            merged_df: pd.DataFrame | None = None

            for channel_id, df in channel_frames:
                # Check for cancellation before processing each channel's DataFrame
                if cancel_event and cancel_event.is_set():
                    logger.info(
                        f"Extraction cancelled during DataFrame merging for FOV {fov}"
                    )
                    return

                if df.empty:
                    continue
                feature_cols = [col for col in df.columns if col not in base_cols]
                rename_map = {col: f"{col}_ch_{channel_id}" for col in feature_cols}
                prepared = df[base_cols + feature_cols].rename(columns=rename_map)
                if merged_df is None:
                    merged_df = prepared
                else:
                    merged_df = merged_df.merge(
                        prepared,
                        on=base_cols,
                        how="outer",
                    )

            if merged_df is None or merged_df.empty:
                logger.info(
                    "FOV %d: Combined trace DataFrame is empty; creating empty CSV with headers",
                    fov,
                )
                # Build column names from base columns + expected feature columns
                expected_columns = ["fov"] + base_cols.copy()
                if pc_features and context.channels:
                    pc_channel = context.channels.get_pc_channel()
                    if pc_channel is not None:
                        for feat in pc_features:
                            expected_columns.append(f"{feat}_ch_{pc_channel}")
                for channel_id, features_list in channel_features.items():
                    for feat in features_list:
                        expected_columns.append(f"{feat}_ch_{channel_id}")
                merged_df = pd.DataFrame(columns=expected_columns)
            else:
                merged_df.sort_values(["cell", "frame", "time"], inplace=True)
                merged_df.insert(0, "fov", fov)
            
            merged_df.to_csv(traces_output_path, index=False, float_format="%.6f")

            fov_paths.traces = traces_output_path
        finally:
            try:
                del seg_labeled
            except Exception:
                pass
