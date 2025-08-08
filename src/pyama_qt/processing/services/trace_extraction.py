"""
Trace extraction processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from numpy.lib.format import open_memmap
from PySide6.QtCore import QObject

from .base import BaseProcessingService
from ..utils.traces import extract_traces_with_tracking, filter_traces_by_length


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
            min_trace_length = params.get("min_trace_length", 3)

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

            segmentation_data = open_memmap(segmentation_path, mode='r')

            # Load corrected fluorescence data from FOV subdirectory
            fluorescence_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "fluorescence_corrected"
            )
            if not fluorescence_path.exists():
                # Check if it's a phase contrast only dataset
                skip_msg = f"FOV {fov_index}: No fluorescence data found, skipping trace extraction"
                self.logger.info(skip_msg)
                self.status_updated.emit(skip_msg)
                return True

            fluorescence_data = open_memmap(fluorescence_path, mode='r')

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
                traces = extract_traces_with_tracking(
                    fluorescence_data, segmentation_data, progress_callback
                )
            except InterruptedError:
                return False

            # Filter traces by minimum length
            if min_trace_length > 0:
                traces = filter_traces_by_length(traces, min_trace_length)
                filter_msg = f"FOV {fov_index}: Filtered traces (min length: {min_trace_length})"
                self.logger.info(filter_msg)
                self.status_updated.emit(filter_msg)

            # Save traces to CSV in FOV subdirectory
            traces_csv_path = fov_dir / f"{base_name}_fov{fov_index:04d}_traces.csv"
            self._save_traces_to_csv(traces, traces_csv_path, fov_index)

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
        self, traces: dict[int, dict[str, list]], output_path: Path, fov_index: int
    ):
        """Save cellular traces to CSV format, only including frames where cells exist."""
        trace_data = []

        for cell_id, cell_traces in traces.items():
            n_timepoints = len(cell_traces["intensity_total"])

            for frame_idx in range(n_timepoints):
                # Only save entries where the cell actually exists (non-NaN values)
                if not np.isnan(cell_traces["intensity_total"][frame_idx]):
                    trace_data.append(
                        {
                            "fov": fov_index,
                            "cell_id": cell_id,
                            "frame": frame_idx,
                            "intensity_total": cell_traces["intensity_total"][frame_idx],
                            "area": cell_traces["area"][frame_idx],
                            "centroid_x": cell_traces["centroid_x"][frame_idx],
                            "centroid_y": cell_traces["centroid_y"][frame_idx],
                        }
                    )

        # Save to CSV
        df = pd.DataFrame(trace_data)
        df.to_csv(output_path, index=False)

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
        return "Background Correction"
