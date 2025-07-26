"""
Trace extraction processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
import numpy as np
import pandas as pd
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
        nd2_path: str,
        fov_index: int,
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
    ) -> bool:
        """
        Process a single field of view: load data, perform tracking and feature extraction,
        and save traces using the traces utility functions.

        Args:
            nd2_path: Path to ND2 file (not used directly, data comes from previous steps)
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

            # Get metadata
            base_name = data_info["filename"].replace(".nd2", "")

            self.status_updated.emit(f"FOV {fov_index + 1}: Loading input data...")

            # Load segmentation data (from binarization step)
            segmentation_path = output_dir / self.get_output_filename(
                base_name, fov_index, "binarized"
            )
            if not segmentation_path.exists():
                raise FileNotFoundError(
                    f"Segmentation data not found: {segmentation_path}"
                )

            segmentation_data = np.load(segmentation_path, mmap_mode="r")["arr_0"]

            # Load corrected fluorescence data (from background correction step)
            fluorescence_path = output_dir / self.get_output_filename(
                base_name, fov_index, "fluorescence_corrected"
            )
            if not fluorescence_path.exists():
                raise FileNotFoundError(
                    f"Corrected fluorescence data not found: {fluorescence_path}"
                )

            fluorescence_data = np.load(fluorescence_path, mmap_mode="r")["arr_0"]

            # Perform tracking and feature extraction in one step
            self.status_updated.emit(
                f"FOV {fov_index + 1}: Performing tracking and feature extraction..."
            )
            traces = extract_traces_with_tracking(fluorescence_data, segmentation_data)

            # Filter traces by minimum length
            if min_trace_length > 0:
                traces = filter_traces_by_length(traces, min_trace_length)
                self.status_updated.emit(
                    f"FOV {fov_index + 1}: Filtered traces (min length: {min_trace_length})"
                )

            # Save traces to CSV
            traces_csv_path = output_dir / f"{base_name}_fov{fov_index:04d}_traces.csv"
            self._save_traces_to_csv(traces, traces_csv_path, fov_index)

            self.status_updated.emit(f"FOV {fov_index + 1} trace extraction completed")
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
        """Save cellular traces to CSV format."""
        trace_data = []

        for cell_id, cell_traces in traces.items():
            n_timepoints = len(cell_traces["intensity_mean"])

            for frame_idx in range(n_timepoints):
                trace_data.append(
                    {
                        "fov": fov_index,
                        "cell_id": cell_id,
                        "frame": frame_idx,
                        "intensity_mean": cell_traces["intensity_mean"][frame_idx],
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
        self, data_info: dict[str, object], output_dir: Path
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
            trace_files.append(output_dir / f"{base_name}_fov{fov_idx:04d}_traces.csv")

        return {"traces": trace_files}

    def requires_previous_step(self) -> str | None:
        """
        Return the name of the required previous processing step.

        Returns:
            str: Name of required previous step
        """
        return "Background Correction"
