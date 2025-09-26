"""Typed state containers used by the processing UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    from pyama_core.io import MicroscopyMetadata
except ImportError:  # pragma: no cover - fallback for docs/tests
    MicroscopyMetadata = object  # type: ignore[misc,assignment]


@dataclass(slots=True)
class ProcessingParameters:
    """User-configurable workflow parameters."""

    fov_start: int = -1
    fov_end: int = -1
    batch_size: int = 2
    n_workers: int = 2


@dataclass(slots=True)
class ChannelSelection:
    """Selected channels for processing."""

    phase: int | None = None
    fluorescence: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ProcessingState:
    """Aggregate state for the processing page."""

    microscopy_path: Path | None = None
    metadata: MicroscopyMetadata | None = None
    output_dir: Path | None = None
    channels: ChannelSelection = field(default_factory=ChannelSelection)
    parameters: ProcessingParameters = field(default_factory=ProcessingParameters)
    is_processing: bool = False
    status_message: str = ""
    error_message: str = ""
    merge_status: str = ""  # New field for merge feedback
