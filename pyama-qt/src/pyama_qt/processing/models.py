import logging
from pathlib import Path
from dataclasses import dataclass

from pyama_core.io import MicroscopyMetadata

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChannelSelection:
    phase: int | None
    fluorescence: list[int]


@dataclass(slots=True)
class WorkflowStartRequest:
    """Request to start processing workflow."""

    microscopy_path: Path
    output_dir: Path
    phase: int | None = None
    fluorescence: list[int] | None = None
    fov_start: int = -1
    fov_end: int = -1
    batch_size: int = 2
    n_workers: int = 2


@dataclass(slots=True)
class MergeRequest:
    """Request to merge processing results."""

    sample_yaml: Path
    processing_results: Path
    input_dir: Path
    output_dir: Path


class ProcessingConfigModel(QObject):
    """Model for processing configuration: paths, metadata, channels, parameters."""

    microscopyPathChanged = Signal(Path)
    metadataChanged = Signal(object)
    outputDirChanged = Signal(Path)
    phaseChanged = Signal(int)
    fluorescenceChanged = Signal(list)
    fovStartChanged = Signal(int)
    fovEndChanged = Signal(int)
    batchSizeChanged = Signal(int)
    nWorkersChanged = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.microscopy_path: Path | None = None
        self.metadata: MicroscopyMetadata | None = None
        self.output_dir: Path | None = None
        self.phase: int | None = None
        self.fluorescence: list[int] | None = None
        self.fov_start: int = -1
        self.fov_end: int = -1
        self.batch_size: int = 2
        self.n_workers: int = 2

    def microscopy_path(self) -> Path | None:
        return self.microscopy_path

    def set_microscopy_path(self, path: Path | None) -> None:
        if self.microscopy_path == path:
            return
        self.microscopy_path = path
        self.microscopyPathChanged.emit(path)

    def load_microscopy(self, path: Path) -> None:
        """Load microscopy metadata from path."""
        logger.info("Loading microscopy from %s", path)
        try:
            # Assume import pyama_core.io.microscopy; metadata = load_microscopy(path)
            # For now, placeholder
            self.microscopy_path = path
            self.metadata = None  # Load actual metadata here
            self.metadataChanged.emit(self.metadata)
            self.microscopyPathChanged.emit(path)
        except Exception:
            logger.exception("Failed to load microscopy")
            raise

    def metadata(self) -> MicroscopyMetadata | None:
        return self.metadata

    def output_dir(self) -> Path | None:
        return self.output_dir

    def set_output_dir(self, path: Path | None) -> None:
        if self.output_dir == path:
            return
        self.output_dir = path
        self.outputDirChanged.emit(path)

    def phase(self) -> int | None:
        return self.phase

    def set_phase(self, phase: int | None) -> None:
        if self.phase == phase:
            return
        self.phase = phase
        self.phaseChanged.emit(phase)

    def fluorescence(self) -> list[int] | None:
        return self.fluorescence

    def set_fluorescence(self, fluorescence: list[int] | None) -> None:
        if self.fluorescence == fluorescence:
            return
        self.fluorescence = fluorescence
        self.fluorescenceChanged.emit(self.fluorescence)

    def fov_start(self) -> int:
        return self.fov_start

    def set_fov_start(self, fov_start: int) -> None:
        if self.fov_start == fov_start:
            return
        self.fov_start = fov_start
        self.fovStartChanged.emit(fov_start)

    def fov_end(self) -> int:
        return self.fov_end

    def set_fov_end(self, fov_end: int) -> None:
        if self.fov_end == fov_end:
            return
        self.fov_end = fov_end
        self.fovEndChanged.emit(fov_end)

    def batch_size(self) -> int:
        return self.batch_size

    def set_batch_size(self, batch_size: int) -> None:
        if self.batch_size == batch_size:
            return
        self.batch_size = batch_size
        self.batchSizeChanged.emit(batch_size)

    def n_workers(self) -> int:
        return self.n_workers

    def set_n_workers(self, n_workers: int) -> None:
        if self.n_workers == n_workers:
            return
        self.n_workers = n_workers
        self.nWorkersChanged.emit(n_workers)

    def update_channels(
        self, phase: int | None = None, fluorescence: list[int] | None = None
    ) -> None:
        """Update channel selection."""
        if phase is not None:
            self.set_phase(phase)
        if fluorescence is not None:
            self.set_fluorescence(fluorescence)

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

    def channels(self) -> ChannelSelection:
        return ChannelSelection(
            phase=self._phase, fluorescence=self._fluorescence or []
        )


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
