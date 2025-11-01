"""Extraction context dataclass for feature extraction."""

from dataclasses import dataclass

import numpy as np


@dataclass
class ExtractionContext:
    """Context containing all information needed for feature extraction."""

    image: np.ndarray
    mask: np.ndarray
    background: np.ndarray  # Always present; zeros if no background correction available
    background_weight: float = 0.0  # Weight for background subtraction (default: 0.0)

