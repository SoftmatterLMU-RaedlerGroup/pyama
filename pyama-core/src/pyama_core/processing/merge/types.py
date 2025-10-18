"""Core data structures for merge processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class FeatureMaps:
    """Container for feature values per timepoint and cell."""

    features: Dict[str, Dict[Tuple[float, int], float]]
    times: List[float]
    cells: List[int]
