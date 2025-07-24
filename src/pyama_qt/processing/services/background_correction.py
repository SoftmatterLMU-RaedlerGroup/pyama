"""
Background correction processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject
from nd2reader import ND2Reader

from .base import BaseProcessingService
from ..utils.background_correction import background_schwarzfischer


class BackgroundCorrectionService(BaseProcessingService):
    """Service for background correction of fluorescence microscopy images."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    def get_step_name(self) -> str:
        """Return the name of this processing step."""
        return "Background Correction"

    def process_fov(
        self,
        nd2_path: str,
        fov_index: int,
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
    ) -> bool:
        """
        Process a single field of view: load fluorescence and segmentation frames,
        perform background correction frame by frame, and save corrected fluorescence data.

        Args:
            nd2_path: Path to ND2 file
            fov_index: Field of view index to process
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters containing 'div_horiz', 'div_vert', 'fl_channel'

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract processing parameters
            div_horiz = params.get("div_horiz", 7)
            div_vert = params.get("div_vert", 5)
            fl_channel_idx = params.get("fl_channel", 0)

            # Get metadata
            metadata = data_info["metadata"]
            n_frames = metadata["n_frames"]
            height = metadata["height"]
            width = metadata["width"]
            base_name = data_info["filename"].replace(".nd2", "")

            # Create output file path
            corrected_path = output_dir / self.get_output_filename(
                base_name, fov_index, "fluorescence_corrected"
            )

            # Create memory-mapped array for corrected fluorescence output
            corrected_memmap = self.create_memmap_array(
                shape=(n_frames, height, width),
                dtype=np.float32,  # Background correction outputs float32
                output_path=corrected_path,
            )

            # Load segmentation data (assume it exists from previous binarization step)
            segmentation_path = output_dir / self.get_output_filename(
                base_name, fov_index, "binarized"
            )
            if not segmentation_path.exists():
                raise FileNotFoundError(
                    f"Segmentation data not found: {segmentation_path}"
                )

            # Load segmentation memmap
            segmentation_data = np.load(segmentation_path, mmap_mode="r")["arr_0"]

            # Process frames one by one
            with ND2Reader(nd2_path) as images:
                for frame_idx in range(n_frames):
                    if self._is_cancelled:
                        return False

                    # Load single fluorescence frame for this FOV and channel
                    fluor_frame = images.get_frame_2D(
                        c=fl_channel_idx, t=frame_idx, v=fov_index
                    )

                    # Get corresponding segmentation frame
                    seg_frame = segmentation_data[frame_idx]

                    # Perform background correction on this frame
                    corrected_frame = background_schwarzfischer(
                        fluor_frame.astype(np.float32),
                        seg_frame,
                        div_horiz=div_horiz,
                        div_vert=div_vert,
                    )

                    # Store corrected frame
                    corrected_memmap[frame_idx] = corrected_frame

                    # Update progress within this FOV
                    if (
                        frame_idx % 10 == 0
                    ):  # Update every 10 frames to avoid too frequent updates
                        fov_progress = int((frame_idx + 1) / n_frames * 100)
                        self.status_updated.emit(
                            f"FOV {fov_index + 1}: Correcting frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"
                        )

            # Flush memory-mapped array to disk
            del corrected_memmap

            self.status_updated.emit(
                f"FOV {fov_index + 1} background correction completed"
            )
            return True

        except Exception as e:
            error_msg = (
                f"Error processing FOV {fov_index} in background correction: {str(e)}"
            )
            self.error_occurred.emit(error_msg)
            return False

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

        corrected_files = []

        for fov_idx in range(n_fov):
            corrected_files.append(
                output_dir
                / self.get_output_filename(base_name, fov_idx, "fluorescence_corrected")
            )

        return {"fluorescence_corrected": corrected_files}

    def requires_previous_step(self) -> str | None:
        """
        Return the name of the required previous processing step.

        Returns:
            str: Name of required previous step (binarization for segmentation masks)
        """
        return "Binarization"
