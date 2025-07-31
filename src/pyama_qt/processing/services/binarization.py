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

            # Create FOV subdirectory
            fov_dir = output_dir / f"fov_{fov_index:04d}"
            fov_dir.mkdir(parents=True, exist_ok=True)
            
            # Create output file paths in FOV subdirectory
            binarized_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "binarized"
            )
            phase_contrast_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "phase_contrast"
            )

            # Create memory-mapped arrays for output
            # We'll use np.lib.format.open_memmap which creates proper .npy files
            binarized_memmap = np.lib.format.open_memmap(
                binarized_path,
                mode='w+',
                dtype=np.bool_,
                shape=(n_frames, height, width)
            )
            
            phase_contrast_memmap = np.lib.format.open_memmap(
                phase_contrast_path,
                mode='w+',
                dtype=np.uint16,
                shape=(n_frames, height, width)
            )

            # Process frames one by one, writing directly to memory-mapped arrays
            self.status_updated.emit(f"FOV {fov_index}: Processing phase contrast frames...")
            
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

                    # Handle different bit depths and write directly to memmap
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
                    
                    if frame_idx % 10 == 0:
                        self.status_updated.emit(
                            f"FOV {fov_index}: Loading frame {frame_idx + 1}/{n_frames}"
                        )

            # Define progress callback
            def progress_callback(frame_idx, n_frames, message):
                if self._is_cancelled:
                    raise InterruptedError("Processing cancelled")
                fov_progress = int((frame_idx + 1) / n_frames * 100)
                self.status_updated.emit(
                    f"FOV {fov_index}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"
                )

            # Binarize using the memory-mapped phase contrast data
            self.status_updated.emit(f"FOV {fov_index}: Applying binarization...")
            try:
                # The logarithmic_std_binarization algorithm needs all frames for std calculation
                # So we pass the memmap directly - it will handle paging
                binarized_stack = logarithmic_std_binarization(
                    phase_contrast_memmap, mask_size, progress_callback
                )
                # Write binarized results
                binarized_memmap[:] = binarized_stack
            except InterruptedError:
                return False
            
            # Flush and close memory-mapped arrays
            del phase_contrast_memmap
            del binarized_memmap

            self.status_updated.emit(f"FOV {fov_index} binarization completed")
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
            fov_dir = output_dir / f"fov_{fov_idx:04d}"
            binarized_files.append(
                fov_dir / self.get_output_filename(base_name, fov_idx, "binarized")
            )
            phase_contrast_files.append(
                fov_dir / self.get_output_filename(base_name, fov_idx, "phase_contrast")
            )

        return {"binarized": binarized_files, "phase_contrast": phase_contrast_files}
