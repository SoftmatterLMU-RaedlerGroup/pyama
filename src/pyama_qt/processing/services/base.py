"""
Base processing service classes for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Any
from PySide6.QtCore import QObject, Signal
import threading

from pyama_qt.utils.logging_config import get_logger


class ProcessingService(QObject):  # type: ignore[misc]
    """Base class for all processing services with FOV-by-FOV processing pattern."""

    progress_updated = Signal(int)  # Progress percentage (0-100)
    status_updated = Signal(str)  # Status message
    error_occurred = Signal(str)  # Error message

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._is_cancelled = False
        self._cancel_lock = threading.Lock()  # Thread-safe access to _is_cancelled
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def process_fov(
        self,
        fov_index: int,
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
    ) -> bool:
        """
        Process a single field of view.

        Args:
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
        data_info: dict[str, Any],
        output_dir: Path,
        params: dict[str, Any],
        fov_start: int | None = None,
        fov_end: int | None = None,
    ) -> bool:
        """
        Process all or a range of fields of view.

        Args:
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
                error_msg = (
                    f"Invalid FOV range: {fov_start}-{fov_end} (file has {n_fov} FOVs)"
                )
                self.logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return False

            total_fovs = fov_end - fov_start + 1
            self.logger.info(
                f"Starting {self.get_step_name()} for FOVs {fov_start}-{fov_end}"
            )
            self.status_updated.emit(
                f"Starting {self.get_step_name()} for FOVs {fov_start}-{fov_end}"
            )

            for i, fov_idx in enumerate(range(fov_start, fov_end + 1)):
                with self._cancel_lock:
                    if self._is_cancelled:
                        self.logger.info(f"{self.get_step_name()} cancelled")
                        self.status_updated.emit(f"{self.get_step_name()} cancelled")
                        return False

                self.logger.debug(f"Processing FOV {fov_idx} ({i + 1}/{total_fovs})")
                self.status_updated.emit(
                    f"Processing FOV {fov_idx} ({i + 1}/{total_fovs})"
                )

                success = self.process_fov(fov_idx, data_info, output_dir, params)
                if not success:
                    error_msg = (
                        f"Failed to process FOV {fov_idx} in {self.get_step_name()}"
                    )
                    self.logger.error(error_msg)
                    self.error_occurred.emit(error_msg)
                    return False

                # Update progress
                progress = int((i + 1) / total_fovs * 100)
                self.progress_updated.emit(progress)

            self.logger.info(
                f"{self.get_step_name()} completed successfully for FOVs {fov_start}-{fov_end}"
            )
            self.status_updated.emit(
                f"{self.get_step_name()} completed successfully for FOVs {fov_start}-{fov_end}"
            )
            return True

        except Exception as e:
            error_msg = f"Error in {self.get_step_name()}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
            return False

    def cancel(self):
        """Cancel the current processing operation."""
        with self._cancel_lock:
            self._is_cancelled = True
        self.logger.info(f"Cancelling {self.get_step_name()}...")
        self.status_updated.emit(f"Cancelling {self.get_step_name()}...")


class BaseProcessingService(ProcessingService):
    """Concrete base implementation with common utilities."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

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
