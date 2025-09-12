"""
Trace extraction processing service.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from numpy.lib.format import open_memmap
import logging

from pyama_core.workflow.services.base import BaseProcessingService
from pyama_core.processing.extraction import extract_trace
from pyama_core.io.nikon import ND2Metadata
from pyama_core.workflow.workflow import ProcessingContext


logger = logging.getLogger(__name__)


class ExtractionService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Extraction"

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
    ) -> None:
        base_name = metadata.base_name

        logger.info(f"FOV {fov}: Loading input data...")
        fov_dir = output_dir / f"fov_{fov:04d}"

        seg_labeled_path = fov_dir / f"{base_name}_fov{fov:04d}_seg_labeled.npy"
        if not seg_labeled_path.exists():
            raise FileNotFoundError(
                f"Tracked segmentation data not found: {seg_labeled_path}"
            )
        segmentation_tracked = open_memmap(seg_labeled_path, mode="r")

        fluorescence_path = (
            fov_dir / f"{base_name}_fov{fov:04d}_fluorescence_corrected.npy"
        )
        if not fluorescence_path.exists():
            fluorescence_path = (
                fov_dir / f"{base_name}_fov{fov:04d}_fluorescence_raw.npy"
            )
            if fluorescence_path.exists():
                logger.info(
                    f"FOV {fov}: Using raw fluorescence data (no corrected data available)"
                )
            else:
                logger.info(
                    f"FOV {fov}: No fluorescence data found, skipping trace extraction"
                )
                return

        fluorescence_data = open_memmap(fluorescence_path, mode="r")

        def progress_callback(frame_idx, n_frames, message):
            fov_progress = int((frame_idx + 1) / n_frames * 100)
            progress_msg = f"FOV {fov}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"
            if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                logger.info(progress_msg)

        n_frames = fluorescence_data.shape[0]
        times = np.arange(n_frames, dtype=float)

        logger.info(f"FOV {fov}: Starting feature extraction...")
        try:
            traces_df_existing = extract_trace(
                image=fluorescence_data,
                segmentation_tracked=segmentation_tracked,
                times=times,
                progress_callback=progress_callback,
            )
        except InterruptedError:
            raise InterruptedError("Feature extraction was interrupted")

        try:
            n_frames = int(fluorescence_data.shape[0])
            traces_df_existing.index = traces_df_existing.index.set_names(
                ["cell_id", "frame"]
            )  # type: ignore[assignment]
            all_cells = (
                traces_df_existing.index.get_level_values("cell_id").unique().tolist()
            )
            full_index = pd.MultiIndex.from_product(
                [sorted(all_cells), range(n_frames)], names=["cell_id", "frame"]
            )
            traces_df_full = traces_df_existing.reindex(full_index)
            traces_df_full["exist"] = False
            traces_df_full.loc[traces_df_existing.index, "exist"] = True
            if "good" in traces_df_existing.columns:
                cell_good = (
                    traces_df_existing.reset_index()
                    .groupby("cell_id")["good"]
                    .first()
                    .to_dict()
                )
                cid_index = traces_df_full.index.get_level_values("cell_id")
                traces_df_full["good"] = cid_index.map(cell_good)
            else:
                traces_df_full["good"] = True
        except Exception as build_exc:
            logger.warning(f"Failed to rebuild full time grid: {build_exc}")
            traces_df_full = traces_df_existing.copy()
            if "exist" not in traces_df_full.columns:
                traces_df_full["exist"] = True

        traces_csv_path = fov_dir / f"{base_name}_fov{fov:04d}_traces.csv"
        self._save_traces_to_csv(traces_df_full, traces_csv_path, fov)

        logger.info(f"FOV {fov} trace extraction completed")

    def _save_traces_to_csv(self, traces_df: pd.DataFrame, output_path: Path, fov: int):
        if not isinstance(traces_df.index, pd.MultiIndex) or list(
            traces_df.index.names
        ) != [
            "cell_id",
            "frame",
        ]:
            traces_df = traces_df.copy()
            traces_df.index = traces_df.index.set_names(["cell_id", "frame"])  # type: ignore[assignment]

        df = traces_df.reset_index()
        df["fov"] = fov
        df = df.rename(columns={"cell_id": "cell", "frame": "time"})

        try:
            df["time"] = pd.to_numeric(df["time"], errors="coerce").astype(float)
        except Exception:
            pass

        nan_cols = [
            c for c in df.columns if c not in {"fov", "time", "cell", "good", "exist"}
        ]
        if "exist" in df.columns and nan_cols:
            df.loc[~df["exist"].astype(bool), nan_cols] = np.nan

        base_cols = [
            "fov",
            "time",
            "cell",
            "good",
            "exist",
            "position_x",
            "position_y",
        ]

        remaining = [c for c in df.columns if c not in base_cols]
        final_cols = base_cols + remaining
        df = df[final_cols]
        df.to_csv(output_path, index=False, float_format="%.6f")
