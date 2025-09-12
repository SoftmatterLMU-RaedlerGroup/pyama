"""
Base classes for workflow services (pure Python, no Qt).
"""

from __future__ import annotations

import logging
from pathlib import Path
from pyama_core.io.nikon import ND2Metadata
from pyama_core.workflow.workflow import ProcessingContext


logger = logging.getLogger(__name__)


class BaseProcessingService:
    def __init__(self) -> None:
        self.name = "Processing"

    def progress_callback(self, f: int, t: int, T: int, message: str):
        if t % 30 == 0:
            logger.info(f"FOV {f}: {message}: {t}/{T})")

    def process_fov(
        self,
        metadata: ND2Metadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
    ) -> None:
        raise NotImplementedError

    def process_all_fovs(
        self,
        metadata: ND2Metadata,
        context: ProcessingContext,
        output_dir: Path,
        fov_start: int | None = None,
        fov_end: int | None = None,
    ) -> None:
        n_fovs = metadata.n_fovs

        if fov_start is None:
            fov_start = 0
        if fov_end is None:
            fov_end = n_fovs - 1

        if fov_start < 0 or fov_end >= n_fovs or fov_start > fov_end:
            raise ValueError(
                f"Invalid FOV range: {fov_start}-{fov_end} (file has {n_fovs} FOVs)"
            )

        logger.info(f"Starting {self.name} for FOVs {fov_start}-{fov_end}")

        for f in range(fov_start, fov_end + 1):
            self.process_fov(metadata, context, output_dir, f)

        logger.info(
            f"{self.name} completed successfully for FOVs {fov_start}-{fov_end}"
        )
