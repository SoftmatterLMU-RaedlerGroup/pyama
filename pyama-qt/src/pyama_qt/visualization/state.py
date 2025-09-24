"""Typed state containers for the visualization UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:  # Avoid hard dependency during documentation builds
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - numpy may be unavailable in docs
    np = None  # type: ignore


@dataclass(slots=True)
class VisualizationState:
    """Shared state for the visualization page."""

    project_path: Path | None = None
    project_data: dict | None = None
    current_fov: int | None = None
    selected_channels: list[str] = field(default_factory=list)
    available_channels: list[str] = field(default_factory=list)
    image_cache: dict[str, "np.ndarray"] = field(default_factory=dict)
    current_frame_index: int = 0
    max_frame_index: int = 0
    current_data_type: str = "pc"
    trace_positions: dict[str, dict[int, tuple[float, float]]] = field(default_factory=dict)
    active_trace_id: str | None = None
    trace_data: dict = field(default_factory=dict)
    traces_csv_path: Path | None = None
    is_loading: bool = False
    status_message: str = ""
    error_message: str = ""


@dataclass(slots=True)
class ProjectLoadRequest:
    """Request to load a project from a directory."""

    project_path: Path


@dataclass(slots=True)
class VisualizationRequest:
    """Request to start visualization for a specific FOV."""

    fov_idx: int
    selected_channels: list[str]


@dataclass(slots=True)
class TraceSelectionRequest:
    """Request to change the active trace selection."""

    trace_id: str | None


@dataclass(slots=True)
class FrameNavigationRequest:
    """Request to navigate to a specific frame."""

    frame_index: int


@dataclass(slots=True)
class DataTypeChangeRequest:
    """Request to change the displayed data type."""

    data_type: str