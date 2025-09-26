"""Request dataclasses for visualization actions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ProjectLoadRequest:
    project_path: Path


@dataclass(slots=True)
class VisualizationRequest:
    fov_idx: int
    selected_channels: list[str]


@dataclass(slots=True)
class TraceSelectionRequest:
    trace_id: str | None


@dataclass(slots=True)
class FrameNavigationRequest:
    frame_index: int


@dataclass(slots=True)
class DataTypeChangeRequest:
    data_type: str
