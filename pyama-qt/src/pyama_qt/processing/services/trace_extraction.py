"""
Trace extraction processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
import pandas as pd
from numpy.lib.format import open_memmap
from PySide6.QtCore import QObject

from .base import BaseProcessingService
from pyama_core.processing.utils.traces import extract_traces_with_tracking, filter_traces


class TraceExtractionService(BaseProcessingService):
    """Service for extracting cellular traces from fluorescence microscopy data."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    def get_step_name(self) -> str:
        """Return the name of this processing step."""
        return "Trace Extraction"

    def process_fov(
        self,
        fov_index: int,
        data_info: dict[str, Any],
        output_dir: Path,
        params: dict[str, Any],
    ) -> bool:
        """
        Process a single field of view: load data from NPY files, perform tracking
        and feature extraction, and save traces using the traces utility functions.

        Args:
            fov_index: Field of view index to process
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters containing 'min_trace_length'

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract processing parameters
            min_trace_length = params.get("min_trace_length", 20)

            base_name = data_info["filename"].replace(".nd2", "")

            load_msg = f"FOV {fov_index}: Loading input data..."
            self.logger.info(load_msg)
            self.status_updated.emit(load_msg)

            # Use FOV subdirectory
            fov_dir = output_dir / f"fov_{fov_index:04d}"

            # Load segmentation data from FOV subdirectory
            segmentation_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "binarized"
            )
            if not segmentation_path.exists():
                raise FileNotFoundError(
                    f"Segmentation data not found: {segmentation_path}"
                )

            segmentation_data = open_memmap(segmentation_path, mode="r")

            # Load fluorescence data from FOV subdirectory
            # First try corrected fluorescence (from background correction)
            fluorescence_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "fluorescence_corrected"
            )

            if not fluorescence_path.exists():
                # If no corrected fluorescence, try raw fluorescence (when background correction was skipped)
                fluorescence_path = fov_dir / self.get_output_filename(
                    base_name, fov_index, "fluorescence_raw"
                )
                if fluorescence_path.exists():
                    self.logger.info(
                        f"FOV {fov_index}: Using raw fluorescence data (no background correction applied)"
                    )
                else:
                    # Check if it's a phase contrast only dataset
                    skip_msg = f"FOV {fov_index}: No fluorescence data found, skipping trace extraction"
                    self.logger.info(skip_msg)
                    self.status_updated.emit(skip_msg)
                    return True

            fluorescence_data = open_memmap(fluorescence_path, mode="r")

            # Define progress callback
            def progress_callback(frame_idx, n_frames, message):
                if self._is_cancelled:
                    raise InterruptedError("Processing cancelled")
                fov_progress = int((frame_idx + 1) / n_frames * 100)
                progress_msg = f"FOV {fov_index}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"

                # Log progress (every 30 frames)
                if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                    self.logger.info(progress_msg)

            # Perform tracking and feature extraction in one step
            status_msg = f"FOV {fov_index}: Starting tracking and feature extraction..."
            self.logger.info(status_msg)
            self.status_updated.emit(status_msg)
            try:
                traces_df = extract_traces_with_tracking(
                    fluorescence_data, segmentation_data, progress_callback
                )
            except InterruptedError:
                return False

            # Apply filters and cleanup
            if min_trace_length > 0:
                traces_df = filter_traces(traces_df, min_trace_length)
                filter_msg = f"FOV {fov_index}: Filtered traces (min length: {min_trace_length}), {traces_df.index.get_level_values('cell_id').nunique()} cells remaining"
                self.logger.info(filter_msg)
                self.status_updated.emit(filter_msg)

            # Save traces to CSV in FOV subdirectory
            traces_csv_path = fov_dir / f"{base_name}_fov{fov_index:04d}_traces.csv"
            self._save_traces_to_csv(traces_df, traces_csv_path, fov_index)

            complete_msg = f"FOV {fov_index} trace extraction completed"
            self.logger.info(complete_msg)
            self.status_updated.emit(complete_msg)
            return True

        except Exception as e:
            error_msg = (
                f"Error processing FOV {fov_index} in trace extraction: {str(e)}"
            )
            self.error_occurred.emit(error_msg)
            return False

    def _save_traces_to_csv(
        self, traces_df: pd.DataFrame, output_path: Path, fov_index: int
    ):
        """Save cellular traces to CSV format from DataFrame.

        Args:
            traces_df: DataFrame with MultiIndex (cell_id, frame) containing trace data
            output_path: Path to save the CSV file
            fov_index: Field of view index
        """
        # Reset index to make cell_id and frame regular columns
        df_to_save = traces_df.reset_index()

        # Add FOV column
        df_to_save["fov"] = fov_index

        # Reorder columns to have fov, cell_id, frame first
        cols = df_to_save.columns.tolist()
        # Remove fov, cell_id, frame from their current positions
        cols.remove("fov")
        cols.remove("cell_id")
        cols.remove("frame")
        # Add them at the beginning
        cols = ["fov", "cell_id", "frame"] + cols
        df_to_save = df_to_save[cols]

        # Save to CSV
        df_to_save.to_csv(output_path, index=False)

    def get_expected_outputs(
        self, data_info: dict[str, Any], output_dir: Path
    ) -> dict[str, list]:
        """
        Get expected output files for this processing step.

        Args:
            data_info: Metadata from file loading
            output_dir: Output directory

        Returns:
            Dict with lists of expected output file paths
        """
        base_name = data_info["filename"].replace(".nd2", "")
        n_fov = data_info["metadata"]["n_fov"]

        trace_files = []

        for fov_idx in range(n_fov):
            fov_dir = output_dir / f"fov_{fov_idx:04d}"
            trace_files.append(fov_dir / f"{base_name}_fov{fov_idx:04d}_traces.csv")

        return {"traces": trace_files}

    def requires_previous_step(self) -> str | None:
        """
        Return the name of the required previous processing step.

        Returns:
            str: Name of required previous step
        """
        return "Binarization"
