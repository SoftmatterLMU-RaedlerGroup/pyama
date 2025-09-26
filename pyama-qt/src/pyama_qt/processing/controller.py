"""Controller coordinating processing UI actions and background work."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from pyama_core.io import load_microscopy_file, MicroscopyMetadata
from pyama_core.processing.workflow import run_complete_workflow

from pyama_qt.processing.state import (
    ProcessingParameters,
    ProcessingState,
)
from pyama_qt.services import WorkerHandle, start_worker

logger = logging.getLogger(__name__)


def _format_timepoints(timepoints: list[float]) -> str:
    """Format a list of timepoints for logging, truncating if too long.

    Args:
        timepoints: List of timepoint values

    Returns:
        Formatted string representation of timepoints
    """
    if not timepoints:
        return "[]"

    if len(timepoints) <= 10:
        return str(timepoints)

    # Show first 3, ellipsis, last 3
    return f"[{', '.join(f'{tp:.1f}' for tp in timepoints[:3])}, ..., {', '.join(f'{tp:.1f}' for tp in timepoints[-1:])}]"


class ProcessingController(QObject):
    """Encapsulates processing workflow orchestration for the UI."""

    state_changed = Signal(object)
    workflow_finished = Signal(bool, str)
    workflow_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._state = ProcessingState()
        self._microscopy_loader: WorkerHandle | None = None
        self._workflow_runner: WorkerHandle | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def current_state(self) -> ProcessingState:
        return self._state

    def load_microscopy(self, path: Path) -> None:
        logger.info("Loading microscopy metadata from %s", path)
        self._update_state(
            microscopy_path=path,
            status_message="Loading microscopy metadata…",
            error_message="",
        )

        worker = _MicroscopyLoaderWorker(path)
        worker.loaded.connect(self._on_microscopy_loaded)
        worker.failed.connect(self._on_microscopy_failed)
        handle = start_worker(
            worker, start_method="run", finished_callback=self._on_loader_finished
        )
        self._microscopy_loader = handle

    def set_output_directory(self, directory: Path) -> None:
        logger.info("Selected output directory: %s", directory)
        self._update_state(output_dir=directory, error_message="")

    def update_channels(self, phase: int | None, fluorescence: list[int]) -> None:
        logger.debug(
            "Channel selection updated: phase=%s, fluorescence=%s", phase, fluorescence
        )
        channels = replace(self._state.channels, phase=phase, fluorescence=fluorescence)
        self._update_state(channels=channels)

    def update_parameters(self, params: ProcessingParameters) -> None:
        logger.debug("Parameters updated: %s", params)
        self._update_state(parameters=params)

    def start_workflow(self) -> None:
        if self._state.is_processing:
            logger.warning("Workflow already running; ignoring start request")
            return

        try:
            self._validate_ready()
        except ValueError as exc:  # validation error surfaced to UI
            logger.error("Cannot start workflow: %s", exc)
            self.workflow_failed.emit(str(exc))
            self._update_state(error_message=str(exc))
            return

        metadata = self._state.metadata
        assert metadata is not None  # checked by _validate_ready

        context = {
            "output_dir": self._state.output_dir,
            "channels": {
                "pc": self._state.channels.phase
                if self._state.channels.phase is not None
                else 0,
                "fl": list(self._state.channels.fluorescence),
            },
            "npy_paths": {},
            "params": {},
            "time_units": "",
        }
        params = self._state.parameters

        worker = _WorkflowRunner(
            metadata=metadata,
            context=context,
            params=params,
        )
        worker.finished.connect(self._on_workflow_finished)

        handle = start_worker(
            worker,
            start_method="run",
            finished_callback=self._clear_workflow_handle,
        )
        self._workflow_runner = handle
        self._update_state(
            is_processing=True, status_message="Running workflow…", error_message=""
        )

    def cancel_workflow(self) -> None:
        if self._workflow_runner:
            logger.info("Cancelling workflow")
            self._workflow_runner.stop()
            self._workflow_runner = None
        self._update_state(is_processing=False, status_message="Workflow cancelled")

    def cleanup(self) -> None:
        """Clean up all running threads and resources."""
        # Only need to stop if threads are still running (shouldn't happen normally)
        if self._microscopy_loader:
            logger.debug("Cleaning up microscopy loader (should have finished already)")
            self._microscopy_loader.stop()
            self._microscopy_loader = None

        # Stop workflow runner if running (this one might actually be in progress)
        if self._workflow_runner:
            logger.info("Stopping workflow runner")
            self._workflow_runner.stop()
            self._workflow_runner = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _validate_ready(self) -> None:
        if self._state.metadata is None:
            raise ValueError("Load an ND2 file before starting the workflow")
        if self._state.output_dir is None:
            raise ValueError("Select an output directory before starting the workflow")
        if self._state.channels.phase is None and not self._state.channels.fluorescence:
            raise ValueError("Select at least one channel to process")

        params = self._state.parameters
        metadata = self._state.metadata
        n_fovs = getattr(metadata, "n_fovs", 0)

        if params.fov_start == -1 and params.fov_end == -1:
            pass
        elif params.fov_start == -1 or params.fov_end == -1:
            raise ValueError(
                "Either process all FOVs (-1/-1) or provide explicit start/end values"
            )
        else:
            if params.fov_start < 0:
                raise ValueError("FOV start must be >= 0 or -1 for all")
            if params.fov_end < params.fov_start:
                raise ValueError("FOV end must be >= start")
            if params.fov_end >= n_fovs:
                raise ValueError(
                    f"FOV end ({params.fov_end}) must be less than total FOVs ({n_fovs})"
                )

        if params.batch_size <= 0:
            raise ValueError("Batch size must be positive")
        if params.n_workers <= 0:
            raise ValueError("Number of workers must be positive")

    def _on_microscopy_loaded(self, metadata: MicroscopyMetadata) -> None:
        logger.info("Microscopy metadata loaded:")
        logger.info("  Base name: %s", getattr(metadata, "base_name", "<unknown>"))
        logger.info("  File type: %s", getattr(metadata, "file_type", "unknown"))
        logger.info("  Height: %s", getattr(metadata, "height", "unknown"))
        logger.info("  Width: %s", getattr(metadata, "width", "unknown"))
        logger.info("  Number of frames: %s", getattr(metadata, "n_frames", "unknown"))
        logger.info("  Number of FOVs: %s", getattr(metadata, "n_fovs", "unknown"))
        logger.info(
            "  Number of channels: %s", getattr(metadata, "n_channels", "unknown")
        )
        timepoints = getattr(metadata, "timepoints", None)
        if timepoints is not None:
            logger.info("  Timepoints: %s", _format_timepoints(timepoints))
        else:
            logger.info("  Timepoints: unknown")
        logger.info(
            "  Channel names: %s", getattr(metadata, "channel_names", "unknown")
        )
        logger.info("  Data type: %s", getattr(metadata, "dtype", "unknown"))

        self._update_state(
            metadata=metadata, status_message="ND2 ready", error_message=""
        )

    def _on_microscopy_failed(self, message: str) -> None:
        logger.error("Failed to load ND2: %s", message)
        self._update_state(metadata=None, status_message="", error_message=message)
        self.workflow_failed.emit(message)

    def _on_loader_finished(self) -> None:
        logger.debug("ND2 loader thread finished")
        self._microscopy_loader = None

    def _on_workflow_finished(self, success: bool, message: str) -> None:
        logger.info("Workflow finished (success=%s): %s", success, message)
        self._update_state(is_processing=False, status_message=message)
        self.workflow_finished.emit(success, message)
        if not success:
            self.workflow_failed.emit(message)

    def _clear_workflow_handle(self) -> None:
        logger.debug("Workflow thread finished")
        self._workflow_runner = None

    def _update_state(self, **updates) -> None:
        for key, value in updates.items():
            setattr(self._state, key, value)
        self.state_changed.emit(self._state)


class _MicroscopyLoaderWorker(QObject):
    loaded = Signal(object)
    failed = Signal(str)
    finished = Signal()  # Signal to indicate work is complete

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._cancelled = False

    def cancel(self) -> None:
        """Mark this worker as cancelled."""
        self._cancelled = True

    def run(self) -> None:
        try:
            if self._cancelled:
                self.finished.emit()
                return
            _img, metadata = load_microscopy_file(self._path)
            if not self._cancelled:
                self.loaded.emit(metadata)
        except Exception as exc:  # pragma: no cover - propagate to UI
            if not self._cancelled:
                self.failed.emit(str(exc))
        finally:
            # Always emit finished to quit the thread
            self.finished.emit()


class _WorkflowRunner(QObject):
    finished = Signal(bool, str)

    def __init__(
        self,
        *,
        metadata: MicroscopyMetadata,
        context: dict,
        params: ProcessingParameters,
    ) -> None:
        super().__init__()
        self._metadata = metadata
        self._context = context
        self._params = params

    def run(self) -> None:
        try:
            success = run_complete_workflow(
                self._metadata,
                self._context,
                fov_start=self._params.fov_start,
                fov_end=self._params.fov_end,
                batch_size=self._params.batch_size,
                n_workers=self._params.n_workers,
            )
            if success:
                output_dir = self._context.get("output_dir", "output directory")
                message = f"Results saved to {output_dir}"
                self.finished.emit(True, message)
            else:  # pragma: no cover - defensive branch
                self.finished.emit(False, "Workflow reported failure")
        except Exception as exc:  # pragma: no cover - propagate to UI
            logger.exception("Workflow execution failed")
            self.finished.emit(False, f"Workflow error: {exc}")
