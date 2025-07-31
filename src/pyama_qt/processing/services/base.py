"""
Base processing service classes for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject, Signal
from nd2reader import ND2Reader
import threading


class ProcessingService(QObject):  # type: ignore[misc]
    """Base class for all processing services with FOV-by-FOV processing pattern."""

    progress_updated = Signal(int)  # Progress percentage (0-100)
    status_updated = Signal(str)  # Status message
    step_completed = Signal(str)  # Step name when completed
    error_occurred = Signal(str)  # Error message

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._is_cancelled = False
        self._cancel_lock = threading.Lock()  # Thread-safe access to _is_cancelled

        # Handle CLI usage where signals might not be connected
        self._cli_mode = parent is None

    def process_fov(
        self,
        nd2_path: str,
        fov_index: int,
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
    ) -> bool:
        """
        Process a single field of view.

        Args:
            nd2_path: Path to ND2 file
            fov_index: Field of view index to process
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters

        Returns:
            bool: True if successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement process_fov")

    def get_step_name(self) -> str:
        """Return the name of this processing step."""
        raise NotImplementedError("Subclasses must implement get_step_name")

    def process_all_fovs(
        self,
        nd2_path: str,
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
        fov_start: int | None = None,
        fov_end: int | None = None,
    ) -> bool:
        """
        Process all or a range of fields of view in the ND2 file.

        Args:
            nd2_path: Path to ND2 file
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters
            fov_start: Starting FOV index (inclusive), None for 0
            fov_end: Ending FOV index (inclusive), None for last FOV

        Returns:
            bool: True if all FOVs processed successfully
        """
        try:
            n_fov = data_info["metadata"]["n_fov"]
            
            # Determine FOV range
            if fov_start is None:
                fov_start = 0
            if fov_end is None:
                fov_end = n_fov - 1
                
            # Validate range
            if fov_start < 0 or fov_end >= n_fov or fov_start > fov_end:
                error_msg = f"Invalid FOV range: {fov_start}-{fov_end} (file has {n_fov} FOVs)"
                self.error_occurred.emit(error_msg)
                return False
                
            total_fovs = fov_end - fov_start + 1
            self.status_updated.emit(f"Starting {self.get_step_name()} for FOVs {fov_start}-{fov_end}")

            for i, fov_idx in enumerate(range(fov_start, fov_end + 1)):
                with self._cancel_lock:
                    if self._is_cancelled:
                        self.status_updated.emit(f"{self.get_step_name()} cancelled")
                        return False

                self.status_updated.emit(f"Processing FOV {fov_idx} ({i + 1}/{total_fovs})")

                success = self.process_fov(
                    nd2_path, fov_idx, data_info, output_dir, params
                )
                if not success:
                    error_msg = (
                        f"Failed to process FOV {fov_idx} in {self.get_step_name()}"
                    )
                    self.error_occurred.emit(error_msg)
                    return False

                # Update progress
                progress = int((i + 1) / total_fovs * 100)
                self.progress_updated.emit(progress)

            self.status_updated.emit(f"{self.get_step_name()} completed successfully")
            self.step_completed.emit(self.get_step_name())
            return True

        except Exception as e:
            error_msg = f"Error in {self.get_step_name()}: {str(e)}"
            self.error_occurred.emit(error_msg)
            return False

    def cancel(self):
        """Cancel the current processing operation."""
        with self._cancel_lock:
            self._is_cancelled = True
        self.status_updated.emit(f"Cancelling {self.get_step_name()}...")


class BaseProcessingService(ProcessingService):
    """Concrete base implementation with common utilities."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    def create_memmap_array(
        self, shape: tuple, dtype: np.dtype, output_path: Path
    ) -> np.memmap:
        """
        Create a memory-mapped numpy array for efficient large file handling.

        Args:
            shape: Array shape (e.g., (n_frames, height, width))
            dtype: Data type for the array
            output_path: Path where the memmap file will be saved

        Returns:
            np.memmap: Memory-mapped array
        """
        return np.memmap(output_path, dtype=dtype, mode="w+", shape=shape)

    def load_fov_frames(
        self, nd2_path: str, fov_index: int, channel_index: int, n_frames: int
    ) -> np.ndarray:
        """
        Load all frames for a specific FOV and channel.

        Args:
            nd2_path: Path to ND2 file
            fov_index: Field of view index
            channel_index: Channel index
            n_frames: Number of frames to load

        Returns:
            np.ndarray: Array with shape (n_frames, height, width)
        """
        frames = []
        with ND2Reader(nd2_path) as images:
            for frame_idx in range(n_frames):
                # Use get_frame_2D method for consistent indexing
                frame = images.get_frame_2D(c=channel_index, t=frame_idx, v=fov_index)
                frames.append(frame)

        return np.array(frames)

    def get_output_filename(self, base_name: str, fov_index: int, suffix: str) -> str:
        """
        Generate standardized output filename.

        Args:
            base_name: Base filename from ND2 file
            fov_index: Field of view index
            suffix: Suffix to append (e.g., 'binarized', 'phase_contrast')

        Returns:
            str: Generated filename
        """
        return f"{base_name}_fov{fov_index:04d}_{suffix}.npy"
