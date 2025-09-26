"""
TypedDict types shared across workflow services to avoid circular imports.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict


class Channels(TypedDict, total=False):
    pc: int
    fl: list[int]


class ResultsPathsPerFOV(TypedDict, total=False):
    # Channel-indexed tuples to clearly identify source/outputs
    # pc uses the phase contrast channel index
    pc: tuple[int, Path]
    # Fluorescence channels: list of (channel_index, path)
    fl: list[tuple[int, Path]]
    # Per-phase-contrast segmentation outputs are single tuples
    # (pc_channel_index, path)
    seg: tuple[int, Path]
    seg_labeled: tuple[int, Path]
    # Background corrected fluorescence: (fluor_channel_index, path)
    fl_corrected: list[tuple[int, Path]]
    # Extracted traces per fluorescence channel: (fluor_channel_index, path)
    traces_csv: list[tuple[int, Path]]


class ProcessingContext(TypedDict, total=False):
    output_dir: Path
    channels: Channels
    results_paths: dict[int, ResultsPathsPerFOV]
    params: dict
    time_units: str


__all__ = [
    "Channels",
    "ResultsPathsPerFOV",
    "ProcessingContext",
]
