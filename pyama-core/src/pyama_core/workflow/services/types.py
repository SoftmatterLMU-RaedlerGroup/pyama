"""
TypedDict types shared across workflow services to avoid circular imports.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict


class Channels(TypedDict, total=False):
    phase_contrast: int
    fluorescence: list[int]


class NpyPathsForFov(TypedDict, total=False):
    # Channel-indexed tuples to clearly identify source/outputs
    # phase_contrast uses the phase contrast channel index
    phase_contrast: tuple[int, Path]
    # Fluorescence channels: list of (channel_index, path)
    fluorescence: list[tuple[int, Path]]
    # Per-phase-contrast segmentation outputs are single tuples
    # (pc_channel_index, path)
    seg: tuple[int, Path]
    seg_labeled: tuple[int, Path]
    # Background corrected fluorescence: (fluor_channel_index, path)
    fluorescence_corrected: list[tuple[int, Path]]
    # Extracted traces per fluorescence channel: (fluor_channel_index, path)
    traces_csv: list[tuple[int, Path]]


class ProcessingContext(TypedDict, total=False):
    output_dir: Path
    channels: Channels
    npy_paths: dict[int, NpyPathsForFov]
    params: dict


__all__ = [
    "Channels",
    "NpyPathsForFov",
    "ProcessingContext",
]
