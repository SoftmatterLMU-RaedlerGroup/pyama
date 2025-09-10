"""
Trace extraction processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from numpy.lib.format import open_memmap
from PySide6.QtCore import QObject

from ..base import BaseProcessingService
from pyama_core.processing.extraction import extract_trace
from pyama_core.io.nikon import ND2Metadata
import logging

logger = logging.getLogger(__name__)


class ExtractionService(BaseProcessingService):
    """Service for extracting cellular traces from fluorescence microscopy data."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.name = "Extraction"

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: dict[str, Any],
        output_dir: Path,
        fov: int,
    ) -> None:
        """
        Process a single field of view: load fluorescence and seg_labeled data from NPY files,
        perform feature extraction using extract_trace, and save traces to CSV.

        Args:
            metadata: Metadata from file loading
            context: Processing context (unused)
            output_dir: Output directory for results
            fov: Field of view index to process
        """
        try:
            base_name = metadata.base_name

            load_msg = f"FOV {fov}: Loading input data..."
            logger.info(load_msg)

            # Use FOV subdirectory
            fov_dir = output_dir / f"fov_{fov:04d}"

            # Load seg_labeled data from FOV subdirectory (output from tracking step)
            seg_labeled_path = fov_dir / f"{base_name}_fov{fov:04d}_seg_labeled.npy"
            if not seg_labeled_path.exists():
                raise FileNotFoundError(
                    f"Tracked segmentation data not found: {seg_labeled_path}"
                )

            segmentation_tracked = open_memmap(seg_labeled_path, mode="r")

            # Load fluorescence data from FOV subdirectory
            # First try corrected fluorescence (from background correction)
            fluorescence_path = (
                fov_dir / f"{base_name}_fov{fov:04d}_fluorescence_corrected.npy"
            )

            if not fluorescence_path.exists():
                # If no corrected fluorescence, try raw fluorescence (when background correction was skipped)
                fluorescence_path = (
                    fov_dir / f"{base_name}_fov{fov:04d}_fluorescence_raw.npy"
                )
                if fluorescence_path.exists():
                    logger.info(
                        f"FOV {fov}: Using raw fluorescence data (no corrected data available)"
                    )
                else:
                    # Check if it's a phase contrast only dataset
                    skip_msg = f"FOV {fov}: No fluorescence data found, skipping trace extraction"
                    logger.info(skip_msg)
                    return

            fluorescence_data = open_memmap(fluorescence_path, mode="r")

            # Define progress callback
            def progress_callback(frame_idx, n_frames, message):
                fov_progress = int((frame_idx + 1) / n_frames * 100)
                progress_msg = f"FOV {fov}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"

                # Log progress (every 30 frames)
                if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                    logger.info(progress_msg)

            # Generate time array for the frames (use frame indices if no timing context)
            n_frames = fluorescence_data.shape[0]
            times = np.arange(n_frames, dtype=float)

            # Perform feature extraction using new extract_trace API
            status_msg = f"FOV {fov}: Starting feature extraction..."
            logger.info(status_msg)
            try:
                traces_df_existing = extract_trace(
                    image=fluorescence_data,
                    segmentation_tracked=segmentation_tracked,
                    times=times,
                    progress_callback=progress_callback,
                )
            except InterruptedError:
                raise InterruptedError("Feature extraction was interrupted")

            # Rebuild full (cell, frame) grid and compute 'exist' flags
            try:
                n_frames = int(fluorescence_data.shape[0])
                # Ensure expected index names
                traces_df_existing.index = traces_df_existing.index.set_names(
                    ["cell_id", "frame"]
                )  # type: ignore[assignment]
                all_cells = (
                    traces_df_existing.index.get_level_values("cell_id")
                    .unique()
                    .tolist()
                )
                full_index = pd.MultiIndex.from_product(
                    [sorted(all_cells), range(n_frames)], names=["cell_id", "frame"]
                )
                # Join to full index
                traces_df_full = traces_df_existing.reindex(full_index)
                # exist flag: True where data existed, False otherwise
                traces_df_full["exist"] = False
                traces_df_full.loc[traces_df_existing.index, "exist"] = True
                # Ensure 'good' is filled per cell for non-existing frames
                if "good" in traces_df_existing.columns:
                    cell_good = (
                        traces_df_existing.reset_index()
                        .groupby("cell_id")["good"]
                        .first()
                        .to_dict()
                    )
                    # Map per index
                    cid_index = traces_df_full.index.get_level_values("cell_id")
                    traces_df_full["good"] = cid_index.map(cell_good)
                else:
                    traces_df_full["good"] = True
            except Exception as build_exc:
                logger.warning(f"Failed to rebuild full time grid: {build_exc}")
                traces_df_full = traces_df_existing.copy()
                if "exist" not in traces_df_full.columns:
                    traces_df_full["exist"] = True

            # Save traces to CSV in FOV subdirectory
            traces_csv_path = fov_dir / f"{base_name}_fov{fov:04d}_traces.csv"
            self._save_traces_to_csv(traces_df_full, traces_csv_path, fov)

            complete_msg = f"FOV {fov} trace extraction completed"
            logger.info(complete_msg)

        except Exception as e:
            error_msg = f"Error processing FOV {fov} in trace extraction: {str(e)}"
            logger.error(error_msg)
            raise

    def _save_traces_to_csv(self, traces_df: pd.DataFrame, output_path: Path, fov: int):
        """Save traces to CSV in the requested wide-per-time format.

        Format:
        - Columns: fov, time, cell, good, exist, position_x, position_y, <features...>
        - Contains all time points for each cell with 'exist' indicating presence.

        Args:
            traces_df: DataFrame with MultiIndex (cell_id, frame) and columns
                ['exist', 'good', 'position_x', 'position_y', <features...>]
            output_path: Path to save the CSV file
            fov: Field of view index
        """
        if not isinstance(traces_df.index, pd.MultiIndex) or list(
            traces_df.index.names
        ) != [
            "cell_id",
            "frame",
        ]:
            # Defensive: ensure expected structure
            traces_df = traces_df.copy()
            traces_df.index = traces_df.index.set_names(["cell_id", "frame"])  # type: ignore[assignment]

        # Reset index to turn cell_id and frame into columns
        df = traces_df.reset_index()

        # Add FOV column and rename id/time columns to requested names
        df["fov"] = fov
        df = df.rename(columns={"cell_id": "cell", "frame": "time"})

        # Ensure 'time' is numeric (float) for downstream compatibility
        try:
            df["time"] = pd.to_numeric(df["time"], errors="coerce").astype(float)
        except Exception:
            pass

        # Ensure NaN for features/positions when exist is False
        nan_cols = [
            c for c in df.columns if c not in {"fov", "time", "cell", "good", "exist"}
        ]
        if "exist" in df.columns and nan_cols:
            df.loc[~df["exist"].astype(bool), nan_cols] = np.nan

        # Determine final column order
        base_cols = [
            "fov",
            "time",
            "cell",
            "good",
            "exist",
            "position_x",
            "position_y",
        ]

        # Include any remaining feature columns after the base ones, preserving existing order
        remaining = [c for c in df.columns if c not in base_cols]
        final_cols = base_cols + remaining
        df = df[final_cols]

        # Save to CSV
        df.to_csv(output_path, index=False, float_format="%.6f")
