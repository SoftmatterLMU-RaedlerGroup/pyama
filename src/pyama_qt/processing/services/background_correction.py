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
        Process a single field of view: load all fluorescence and segmentation frames,
        perform temporal background correction, and save corrected fluorescence data.

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
            fl_channel_idx = data_info.get("fl_channel", 0)

            # Get metadata
            metadata = data_info["metadata"]
            n_frames = metadata["n_frames"]
            height = metadata["height"]
            width = metadata["width"]
            base_name = data_info["filename"].replace(".nd2", "")

            # Use FOV subdirectory
            fov_dir = output_dir / f"fov_{fov_index:04d}"
            
            # Create output file path in FOV subdirectory
            corrected_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "fluorescence_corrected"
            )

            # Load segmentation data from FOV subdirectory
            segmentation_path = fov_dir / self.get_output_filename(
                base_name, fov_index, "binarized"
            )
            if not segmentation_path.exists():
                raise FileNotFoundError(
                    f"Segmentation data not found: {segmentation_path}"
                )

            # Load segmentation data (memory-mapped .npy file)
            segmentation_data = np.load(segmentation_path, mmap_mode="r")

            # Create memory-mapped array for fluorescence input data
            fluor_path = fov_dir / f"{base_name}_fov{fov_index:04d}_fluorescence_temp.npy"
            fluor_memmap = np.lib.format.open_memmap(
                fluor_path,
                mode='w+',
                dtype=np.float32,
                shape=(n_frames, height, width)
            )
            
            self.status_updated.emit(f"FOV {fov_index}: Loading fluorescence frames...")
            
            # Load fluorescence frames directly into memmap
            with ND2Reader(nd2_path) as images:
                for frame_idx in range(n_frames):
                    if self._is_cancelled:
                        del fluor_memmap
                        fluor_path.unlink(missing_ok=True)
                        return False

                    # Load single fluorescence frame for this FOV and channel
                    fluor_frame = images.get_frame_2D(
                        c=fl_channel_idx, t=frame_idx, v=fov_index
                    )
                    fluor_memmap[frame_idx] = fluor_frame.astype(np.float32)

                    if frame_idx % 10 == 0:
                        self.status_updated.emit(
                            f"FOV {fov_index}: Loading frame {frame_idx + 1}/{n_frames}"
                        )

            # Create output memory-mapped array
            corrected_memmap = np.lib.format.open_memmap(
                corrected_path,
                mode='w+',
                dtype=np.float32,
                shape=(n_frames, height, width)
            )

            # Define progress callback
            def progress_callback(frame_idx, n_frames, message):
                if self._is_cancelled:
                    raise InterruptedError("Processing cancelled")
                fov_progress = int((frame_idx + 1) / n_frames * 100)
                self.status_updated.emit(
                    f"FOV {fov_index}: {message} frame {frame_idx + 1}/{n_frames} ({fov_progress}%)"
                )

            # Perform temporal background correction using memory-mapped arrays
            self.status_updated.emit(f"FOV {fov_index}: Starting temporal background correction...")
            try:
                # The algorithm will work with memory-mapped arrays
                # OS will handle paging as needed
                # Pass the output memmap directly to avoid creating another copy
                background_schwarzfischer(
                    fluor_memmap,
                    segmentation_data,
                    div_horiz=div_horiz,
                    div_vert=div_vert,
                    progress_callback=progress_callback,
                    output_array=corrected_memmap
                )
            except InterruptedError:
                del fluor_memmap
                del corrected_memmap
                fluor_path.unlink(missing_ok=True)
                return False

            # Clean up
            self.status_updated.emit(f"FOV {fov_index}: Cleaning up...")
            del fluor_memmap
            del corrected_memmap
            fluor_path.unlink(missing_ok=True)  # Remove temporary file

            self.status_updated.emit(
                f"FOV {fov_index} background correction completed"
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
            fov_dir = output_dir / f"fov_{fov_idx:04d}"
            corrected_files.append(
                fov_dir / self.get_output_filename(base_name, fov_idx, "fluorescence_corrected")
            )

        return {"fluorescence_corrected": corrected_files}

    def requires_previous_step(self) -> str | None:
        """
        Return the name of the required previous processing step.

        Returns:
            str: Name of required previous step (binarization for segmentation masks)
        """
        return "Binarization"
