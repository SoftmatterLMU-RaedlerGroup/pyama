"""Typed state containers used by the processing UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from pyama_core.io import ND2Metadata
except ImportError:  # pragma: no cover - fallback for docs/tests
    ND2Metadata = object  # type: ignore[misc,assignment]


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

    phase: Optional[int] = None
    fluorescence: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ProcessingState:
    """Aggregate state for the processing page."""

    nd2_path: Optional[Path] = None
    metadata: Optional[ND2Metadata] = None
    output_dir: Optional[Path] = None
    channels: ChannelSelection = field(default_factory=ChannelSelection)
    parameters: ProcessingParameters = field(default_factory=ProcessingParameters)
    is_processing: bool = False
    status_message: str = ""
    error_message: str = ""
