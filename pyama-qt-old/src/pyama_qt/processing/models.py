from __future__ import annotations

import logging
from pathlib import Path
from typing import List
from dataclasses import dataclass, field

try:
    from pyama_core.io import MicroscopyMetadata
except ImportError:  # pragma: no cover - fallback for docs/tests
    MicroscopyMetadata = object  # type: ignore[misc,assignment]

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


@dataclass
class ChannelSelection:
    phase: int | None = None
    fluorescence: list[int] = field(default_factory=list)


@dataclass
class Parameters:
    fov_start: int
    fov_end: int
    batch_size: int
    n_workers: int


class ProcessingConfigModel(QObject):
    """Model for processing configuration: paths, metadata, channels, parameters."""

    microscopyPathChanged = Signal(Path)
    metadataChanged = Signal(object)  # MicroscopyMetadata
    outputDirChanged = Signal(Path)
    phaseChanged = Signal(int)
    fluorescenceChanged = Signal(list)
    fovStartChanged = Signal(int)
    fovEndChanged = Signal(int)
    batchSizeChanged = Signal(int)
    nWorkersChanged = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._microscopy_path: Path | None = None
        self._metadata: MicroscopyMetadata | None = None
        self._output_dir: Path | None = None
        self._phase: int | None = None
        self._fluorescence: List[int] = []
        self._fov_start: int = -1
        self._fov_end: int = -1
        self._batch_size: int = 2
        self._n_workers: int = 2

    def microscopy_path(self) -> Path | None:
        return self._microscopy_path

    def set_microscopy_path(self, path: Path | None) -> None:
        if self._microscopy_path == path:
            return
        self._microscopy_path = path
        self.microscopyPathChanged.emit(path)

    def set_metadata(self, metadata: MicroscopyMetadata | None) -> None:
        """Set metadata from microscopy loading."""
        if self._metadata is metadata:
            return
        self._metadata = metadata
        self.metadataChanged.emit(metadata)

    def load_microscopy(self, path: Path) -> None:
        """Load microscopy metadata from path."""
        logger.info("Loading microscopy from %s", path)
        try:
            # Initialize with empty metadata which will be populated by worker
            self._microscopy_path = path
            self.set_metadata(None)  # Clear any previous metadata
            self.microscopyPathChanged.emit(path)
        except Exception:
            logger.exception("Failed to load microscopy")
            raise

    def metadata(self) -> MicroscopyMetadata | None:
        return self._metadata

    def output_dir(self) -> Path | None:
        return self._output_dir

    def set_output_dir(self, path: Path | None) -> None:
        if self._output_dir == path:
            return
        self._output_dir = path
        self.outputDirChanged.emit(path)

    def phase(self) -> int | None:
        return self._phase

    def set_phase(self, phase: int | None) -> None:
        if self._phase == phase:
            return
        self._phase = phase
        self.phaseChanged.emit(phase)

    def fluorescence(self) -> List[int] | None:
        return self._fluorescence if self._fluorescence else None

    def set_fluorescence(self, fluorescence: List[int] | None) -> None:
        if fluorescence is None:
            fluorescence = []
        if self._fluorescence == fluorescence:
            return
        self._fluorescence = fluorescence
        self.fluorescenceChanged.emit(self._fluorescence)

    def channels(self) -> ChannelSelection:
        return ChannelSelection(phase=self._phase, fluorescence=self._fluorescence)

    def fov_start(self) -> int:
        return self._fov_start

    def set_fov_start(self, fov_start: int) -> None:
        if self._fov_start == fov_start:
            return
        self._fov_start = fov_start
        self.fovStartChanged.emit(fov_start)

    def fov_end(self) -> int:
        return self._fov_end

    def set_fov_end(self, fov_end: int) -> None:
        if self._fov_end == fov_end:
            return
        self._fov_end = fov_end
        self.fovEndChanged.emit(fov_end)

    def batch_size(self) -> int:
        return self._batch_size

    def set_batch_size(self, batch_size: int) -> None:
        if self._batch_size == batch_size:
            return
        self._batch_size = batch_size
        self.batchSizeChanged.emit(batch_size)

    def n_workers(self) -> int:
        return self._n_workers

    def set_n_workers(self, n_workers: int) -> None:
        if self._n_workers == n_workers:
            return
        self._n_workers = n_workers
        self.nWorkersChanged.emit(n_workers)

    def update_channels(
        self, phase: int | None = None, fluorescence: List[int] | None = None
    ) -> None:
        """Update channel selection."""
        if phase is not None:
            self.set_phase(phase)
        if fluorescence is not None:
            self.set_fluorescence(fluorescence)

    def parameters(self) -> Parameters:
        """Return processing parameters as a structured object."""
        return Parameters(
            fov_start=self._fov_start,
            fov_end=self._fov_end,
            batch_size=self._batch_size,
            n_workers=self._n_workers,
        )

    def update_parameters(
        self,
        fov_start: int | None = None,
        fov_end: int | None = None,
        batch_size: int | None = None,
        n_workers: int | None = None,
    ) -> None:
        """Update processing parameters."""
        if fov_start is not None:
            self.set_fov_start(fov_start)
        if fov_end is not None:
            self.set_fov_end(fov_end)
        if batch_size is not None:
            self.set_batch_size(batch_size)
        if n_workers is not None:
            self.set_n_workers(n_workers)


class WorkflowStatusModel(QObject):
    """Model for workflow execution status and progress."""

    isProcessingChanged = Signal(bool)
    statusMessageChanged = Signal(str)
    errorMessageChanged = Signal(str)
    mergeStatusChanged = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._is_processing: bool = False
        self._status_message: str = ""
        self._error_message: str = ""
        self._merge_status: str = ""

    def is_processing(self) -> bool:
        return self._is_processing

    def set_is_processing(self, value: bool) -> None:
        if self._is_processing == value:
            return
        self._is_processing = value
        self.isProcessingChanged.emit(value)

    def status_message(self) -> str:
        return self._status_message

    def set_status_message(self, message: str) -> None:
        if self._status_message == message:
            return
        self._status_message = message
        self.statusMessageChanged.emit(message)

    def error_message(self) -> str:
        return self._error_message

    def set_error_message(self, message: str) -> None:
        if self._error_message == message:
            return
        self._error_message = message
        self.errorMessageChanged.emit(message)

    def merge_status(self) -> str:
        return self._merge_status

    def set_merge_status(self, status: str) -> None:
        if self._merge_status == status:
            return
        self._merge_status = status
        self.mergeStatusChanged.emit(status)
