"""
Copy service for extracting frames from ND2 files to NPY format.
"""

from pathlib import Path
from PySide6.QtCore import QObject
from functools import partial

from .base import BaseProcessingService
from pyama_core.processing.copying import copy_npy
import logging
from pyama_core.io.nikon import ND2Metadata
from typing import Any

logger = logging.getLogger(__name__)


class CopyingService(BaseProcessingService):
    """Service for copying channels from ND2 files to NPY files."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.name = "Copy"

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: dict[str, Any],
        output_dir: Path,
        f: int,
    ) -> None:
        """
        Process a single field of view: extract and save channel data.

        Args:
            metadata: Metadata from file loading
            context: Context for the processing
            output_dir: Output directory for results
            f: Field of view index to process
            output_dir: Output directory for results

        Returns:
            None
        """
        try:
            context["copying"][f] = copy_npy(
                metadata=metadata,
                f=f,
                channels=context["channels"],
                output_dir=output_dir,
                progress_callback=partial(self.progress_callback, f=f),
            )
            logger.info(f"FOV {f} copy completed")
        except Exception as e:
            logger.exception(f"Error copying FOV {f}: {str(e)}")
            raise e
