"""Core data structures for merge processing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeatureMaps:
    """Container for feature values per timepoint and cell."""

    features: dict[str, dict[tuple[float, int], float]]
    times: list[float]
    cells: list[int]
