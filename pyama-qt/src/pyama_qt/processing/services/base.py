"""
Base processing service classes for PyAMA-Qt microscopy image analysis.
"""

import logging
from pathlib import Path
from PySide6.QtCore import QObject
from pyama_core.io.nikon import ND2Metadata
from typing import Any

logger = logging.getLogger(__name__)


class BaseProcessingService(QObject):
    """Base class for all processing services with FOV-by-FOV processing pattern."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.name = "Processing"  # Default name, should be overridden by subclasses

    def progress_callback(self, f: int, t: int, T: int, message: str):
        if t % 30 == 0:
            logger.info(f"FOV {f}: {message}: {t}/{T})")

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: dict[str, Any],
        output_dir: Path,
        fov: int,
    ) -> None:
        """
        Process a single field of view.

        Args:
            metadata: Metadata from file loading
            context: Context for the processing
            output_dir: Output directory for results
            fov: Field of view index to process

        Returns:
            None
        """
        raise NotImplementedError("Subclasses must implement process_fov")

    def process_all_fovs(
        self,
        metadata: ND2Metadata,
        context: dict[str, Any],
        output_dir: Path,
        fov_start: int | None = None,
        fov_end: int | None = None,
    ) -> None:
        """
        Process all or a range of fields of view.

        Args:
            metadata: Metadata from file loading
            context: Context for the processing
            output_dir: Output directory for results
            fov_start: Starting FOV index (inclusive), None for 0
            fov_end: Ending FOV index (inclusive), None for last FOV

        Returns:
            None
        """
        try:
            n_fovs = metadata.n_fovs

            # Determine FOV range
            if fov_start is None:
                fov_start = 0
            if fov_end is None:
                fov_end = n_fovs - 1

            # Validate range
            if fov_start < 0 or fov_end >= n_fovs or fov_start > fov_end:
                raise ValueError(
                    f"Invalid FOV range: {fov_start}-{fov_end} (file has {n_fovs} FOVs)"
                )

            logger.info(f"Starting {self.name} for FOVs {fov_start}-{fov_end}")

            for f in range(fov_start, fov_end + 1):
                self.process_fov(metadata, output_dir, f)

            logger.info(
                f"{self.name} completed successfully for FOVs {fov_start}-{fov_end}"
            )
        except Exception as e:
            logger.exception(f"Error processing FOVs {fov_start}-{fov_end}")
            raise e
