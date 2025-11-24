"""
Base classes for workflow services (pure Python, no Qt).
"""

import logging
from pathlib import Path
from pyama_core.io import MicroscopyMetadata
from pyama_core.types.processing import (
    ProcessingContext,
    ensure_context,
)


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
        """Log coarse progress for long-running loops (every 30 steps)."""
        if t % 30 == 0:
            logger.info("FOV %d: %s (%d/%d)", f, message, t, T)

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
        cancel_event=None,
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

        logger.info("Starting %s for FOVs %d-%d", self.name, fov_start, fov_end)

        for f in range(fov_start, fov_end + 1):
            # Check for cancellation before processing each FOV
            if cancel_event and cancel_event.is_set():
                logger.info("%s cancelled at FOV %d", self.name, f)
                break
            self.process_fov(metadata, context, output_dir, f, cancel_event)

        logger.info(
            "%s completed successfully for FOVs %d-%d", self.name, fov_start, fov_end
        )
