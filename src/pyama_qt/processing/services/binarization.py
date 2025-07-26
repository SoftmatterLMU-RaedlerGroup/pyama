"""
Binarization processing service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject
from nd2reader import ND2Reader

from .base import BaseProcessingService
from ..utils.binarization import logarithmic_std_binarization


class BinarizationService(BaseProcessingService):
    """Service for binarizing phase contrast microscopy images."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    def get_step_name(self) -> str:
        """Return the name of this processing step."""
        return "Binarization"

    def process_fov(
        self,
        nd2_path: str,
        fov_index: int,
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
    ) -> bool:
        """
        Process a single field of view: load phase contrast frames, binarize each frame,
        and save both binarized and original phase contrast data as 3D NPZ memmaps.

        Args:
            nd2_path: Path to ND2 file
            fov_index: Field of view index to process
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters containing 'mask_size'

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract processing parameters
            mask_size = params.get("mask_size", 3)

            # Get metadata
            metadata = data_info["metadata"]
            n_frames = metadata["n_frames"]
            height = metadata["height"]
            width = metadata["width"]
            pc_channel_idx = data_info["pc_channel"]
            base_name = data_info["filename"].replace(".nd2", "")

            # Create output file paths
            binarized_path = output_dir / self.get_output_filename(
                base_name, fov_index, "binarized"
            )
            phase_contrast_path = output_dir / self.get_output_filename(
                base_name, fov_index, "phase_contrast"
            )

            # Create memory-mapped arrays for output
            binarized_memmap = self.create_memmap_array(
                shape=(n_frames, height, width),
                dtype=np.bool_,
                output_path=binarized_path,
            )

            phase_contrast_memmap = self.create_memmap_array(
                shape=(n_frames, height, width),
                dtype=np.uint16,  # Default to 16-bit, will be cast if needed
                output_path=phase_contrast_path,
            )

            # Process frames one by one
            with ND2Reader(nd2_path) as images:
                for frame_idx in range(n_frames):
                    with self._cancel_lock:
                        if self._is_cancelled:
                            return False

                    # Load single frame for this FOV and phase contrast channel
                    # ND2Reader indexing: [c, t, z, x, y, v]
                    frame = images.get_frame_2D(
                        c=pc_channel_idx, t=frame_idx, v=fov_index
                    )

                    # Store original phase contrast frame (handle different bit depths)
                    if frame.dtype == np.uint8:
                        # Scale 8-bit to 16-bit
                        phase_contrast_memmap[frame_idx] = frame.astype(np.uint16) * 257
                    elif frame.dtype in [np.uint16, np.int16]:
                        phase_contrast_memmap[frame_idx] = frame.astype(np.uint16)
                    else:
                        # For other types, normalize to uint16 range
                        frame_min = frame.min()
                        frame_max = frame.max()
                        if frame_max > frame_min:
                            normalized = (frame - frame_min) / (frame_max - frame_min) * 65535
                            phase_contrast_memmap[frame_idx] = normalized.astype(np.uint16)
                        else:
                            phase_contrast_memmap[frame_idx] = np.zeros_like(frame, dtype=np.uint16)

                    # Binarize the frame using logarithmic std algorithm
                    binarized_frame = logarithmic_std_binarization(frame, mask_size)
                    binarized_memmap[frame_idx] = binarized_frame

                    # Update progress within this FOV
                    if (
                        frame_idx % 10 == 0
                    ):  # Update every 10 frames to avoid too frequent updates
                        fov_progress = int((frame_idx + 1) / n_frames * 100)
                        self.status_updated.emit(
                            f"FOV {fov_index + 1}: Processing frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"
                        )

            # Flush memory-mapped arrays to disk
            binarized_memmap.flush()
            phase_contrast_memmap.flush()
            del binarized_memmap
            del phase_contrast_memmap

            self.status_updated.emit(f"FOV {fov_index + 1} binarization completed")
            return True

        except Exception as e:
            error_msg = f"Error processing FOV {fov_index} in binarization: {str(e)}"
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

        binarized_files = []
        phase_contrast_files = []

        for fov_idx in range(n_fov):
            binarized_files.append(
                output_dir / self.get_output_filename(base_name, fov_idx, "binarized")
            )
            phase_contrast_files.append(
                output_dir
                / self.get_output_filename(base_name, fov_idx, "phase_contrast")
            )

        return {"binarized": binarized_files, "phase_contrast": phase_contrast_files}
