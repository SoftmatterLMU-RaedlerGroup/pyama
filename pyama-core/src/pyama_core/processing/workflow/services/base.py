"""
Base classes for workflow services (pure Python, no Qt).
"""

from __future__ import annotations

import logging
from pathlib import Path
from pyama_core.io import MicroscopyMetadata
from .types import ProcessingContext, ensure_context


logger = logging.getLogger(__name__)


class BaseProcessingService:
    def __init__(self) -> None:
        self.name = "Processing"
        # Optional callable for reporting progress events to a parent process
        # It will be called with a single dict payload built in progress_callback
        self._progress_reporter = None

    def set_progress_reporter(self, reporter):
        """Inject a reporter callable that accepts a single event dict.

        The event dict has keys: step, fov, t, T, message.
        """
        self._progress_reporter = reporter

    def progress_callback(self, f: int, t: int, T: int, message: str):
        if t % 30 == 0:
            logger.info(f"FOV {f}: {message}: {t}/{T})")
            if self._progress_reporter is not None:
                try:
                    event = {
                        "step": self.name,
                        "fov": f,
                        "t": t,
                        "T": T,
                        "message": message,
                    }
                    self._progress_reporter(event)
                except Exception:
                    # Never let progress reporting break the worker
                    pass

    def process_fov(
        self,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
    ) -> None:
        raise NotImplementedError

    def process_all_fovs(
        self,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        output_dir: Path,
        fov_start: int | None = None,
        fov_end: int | None = None,
    ) -> None:
        context = ensure_context(context)
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
