from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(slots=True)
class WorkflowStartRequest:
    """Request to start processing workflow."""

    microscopy_path: Path
    output_dir: Path
    phase: int | None = None
    fluorescence: List[int] | None = None
    fov_start: int = -1
    fov_end: int = -1
    batch_size: int = 2
    n_workers: int = 2


@dataclass(slots=True)
class MergeRequest:
    """Request to merge processing results."""

    input_paths: List[Path]
    output_path: Path
