"""Extraction context dataclass for feature extraction."""

from dataclasses import dataclass

import numpy as np


@dataclass
class ExtractionContext:
    """Context containing all information needed for feature extraction."""

    image: np.ndarray
    mask: np.ndarray
    # background: np.ndarray

