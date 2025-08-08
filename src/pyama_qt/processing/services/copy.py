"""
Copy service for extracting frames from ND2 files to NPY format.
"""

from pathlib import Path
from typing import Any
from PySide6.QtCore import QObject

from .base import BaseProcessingService
from ..utils import copy_channels_to_npy


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
        """Core copy logic for a single FOV delegated to utils with progress callback."""
        metadata = data_info["metadata"]
        n_frames = int(metadata["n_frames"])  # type: ignore[index]

        def progress_callback(frame_idx: int, total_frames: int, message: str):
            # Cancellation support
            with self._cancel_lock:
                if self._is_cancelled:
                    raise InterruptedError("Processing cancelled")

            fov_progress = int((frame_idx + 1) / total_frames * 100) if total_frames else 0
            progress_msg = (
                f"FOV {fov_index}: {message} frame {frame_idx + 1}/{total_frames} ({fov_progress}%)"
            )
            if frame_idx % 30 == 0 or frame_idx == n_frames - 1:
                self.logger.info(progress_msg)

        try:
            copy_channels_to_npy(
                nd2_path=nd2_path,
                fov_index=fov_index,
                data_info=data_info,
                output_dir=output_dir,
                progress_callback=progress_callback,
            )
        except InterruptedError:
            return False

        complete_msg = f"FOV {fov_index} copy completed"
        self.logger.info(complete_msg)
        self.status_updated.emit(complete_msg)
        return True

    # Conversion moved to utils

    def cancel(self):
        """Cancel the current processing operation."""
        super().cancel()

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