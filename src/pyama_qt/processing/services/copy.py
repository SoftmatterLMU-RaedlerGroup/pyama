"""
Copy service for extracting frames from ND2 files to NPY format.
"""

from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject
from nd2reader import ND2Reader

from .base import BaseProcessingService


class CopyService(BaseProcessingService):
    """Service for copying channels from ND2 files to NPY files."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    def get_step_name(self) -> str:
        """Return the name of this processing step."""
        return "Copy"

    def process_batch(
        self,
        nd2_path: str,
        fov_indices: list[int],
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
    ) -> bool:
        """
        Process multiple FOVs sequentially.
        
        Note: Sequential processing is used by default to avoid resource
        contention on the ND2 file. Parallel processing can cause issues
        with ND2 file access.
        
        Args:
            nd2_path: Path to ND2 file
            fov_indices: List of FOV indices to process
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters
            
        Returns:
            bool: True if all FOVs processed successfully
        """
        # Sequential processing to avoid ND2 file contention
        total = len(fov_indices)
        for idx, fov_idx in enumerate(fov_indices):
            if self._is_cancelled:
                return False
                
            if not self.process_fov(nd2_path, fov_idx, data_info, output_dir, params):
                return False
                
            # Update progress
            progress = int((idx + 1) / total * 100)
            self.progress_updated.emit(progress)
            status_msg = f"Copied {idx + 1}/{total} FOVs"
            self.logger.info(status_msg)
            self.status_updated.emit(status_msg)
            
        return True

    # Parallel processing methods removed - sequential processing only
    # to avoid ND2 file resource contention

    def process_fov(
        self,
        nd2_path: str,
        fov_index: int,
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
    ) -> bool:
        """
        Process a single field of view: extract and save channel data.
        
        Args:
            nd2_path: Path to ND2 file
            fov_index: Field of view index to process
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return self._copy_fov_data(nd2_path, fov_index, data_info, output_dir, params)
        except Exception as e:
            error_msg = f"Error copying FOV {fov_index}: {str(e)}"
            self.error_occurred.emit(error_msg)
            return False

    def _copy_fov_data(
        self,
        nd2_path: str,
        fov_index: int,
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
    ) -> bool:
        """Core copy logic for a single FOV."""
        # Get metadata
        metadata = data_info["metadata"]
        n_frames = metadata["n_frames"]
        height = metadata["height"]
        width = metadata["width"]
        pc_channel_idx = data_info["pc_channel"]
        fl_channel_idx = data_info.get("fl_channel")
        base_name = data_info["filename"].replace(".nd2", "")
        
        # Create FOV subdirectory
        fov_dir = output_dir / f"fov_{fov_index:04d}"
        fov_dir.mkdir(parents=True, exist_ok=True)
        
        # Create output file paths
        pc_path = fov_dir / f"{base_name}_fov{fov_index:04d}_phase_contrast_raw.npy"
        fl_path = fov_dir / f"{base_name}_fov{fov_index:04d}_fluorescence_raw.npy" if fl_channel_idx is not None else None
        
        # Create memory-mapped arrays for output
        pc_memmap = np.lib.format.open_memmap(
            pc_path,
            mode='w+',
            dtype=np.uint16,
            shape=(n_frames, height, width)
        )
        
        fl_memmap = None
        if fl_path:
            fl_memmap = np.lib.format.open_memmap(
                fl_path,
                mode='w+',
                dtype=np.uint16,
                shape=(n_frames, height, width)
            )
        
        # Copy frames from ND2
        with ND2Reader(nd2_path) as images:
            for frame_idx in range(n_frames):
                with self._cancel_lock:
                    if self._is_cancelled:
                        return False
                
                # Extract phase contrast
                pc_frame = images.get_frame_2D(
                    c=pc_channel_idx, t=frame_idx, v=fov_index
                )
                pc_memmap[frame_idx] = self._convert_to_uint16(pc_frame)
                
                # Extract fluorescence if present
                if fl_memmap is not None and fl_channel_idx is not None:
                    fl_frame = images.get_frame_2D(
                        c=fl_channel_idx, t=frame_idx, v=fov_index
                    )
                    fl_memmap[frame_idx] = self._convert_to_uint16(fl_frame)
                
                # Log progress periodically
                if frame_idx % 50 == 0:
                    self.logger.info(f"FOV {fov_index}: Copying frame {frame_idx + 1}/{n_frames}")
        
        # Flush and close
        del pc_memmap
        if fl_memmap is not None:
            del fl_memmap
        
        complete_msg = f"FOV {fov_index} copy completed"
        self.logger.info(complete_msg)
        self.status_updated.emit(complete_msg)
        return True

    def _convert_to_uint16(self, frame: np.ndarray) -> np.ndarray:
        """Convert frame to uint16 format."""
        if frame.dtype == np.uint8:
            # Scale 8-bit to 16-bit
            return frame.astype(np.uint16) * 257
        elif frame.dtype in [np.uint16, np.int16]:
            return frame.astype(np.uint16)
        else:
            self.logger.warning(
                f"Unexpected data type {frame.dtype}, attempting direct conversion to uint16. "
                f"This may result in data loss or unexpected behavior."
            )
            return frame.astype(np.uint16)

    def cancel(self):
        """Cancel the current processing operation."""
        super().cancel()

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
        fl_channel_idx = data_info.get("fl_channel")
        
        pc_files = []
        fl_files = []
        
        for fov_idx in range(n_fov):
            fov_dir = output_dir / f"fov_{fov_idx:04d}"
            pc_files.append(
                fov_dir / f"{base_name}_fov{fov_idx:04d}_phase_contrast_raw.npy"
            )
            if fl_channel_idx is not None:
                fl_files.append(
                    fov_dir / f"{base_name}_fov{fov_idx:04d}_fluorescence_raw.npy"
                )
        
        result = {"phase_contrast_raw": pc_files}
        if fl_files:
            result["fluorescence_raw"] = fl_files
        return result