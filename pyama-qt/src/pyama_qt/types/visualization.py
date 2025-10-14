"""Visualization-related data structures."""

# =============================================================================
# IMPORTS
# =============================================================================

from dataclasses import dataclass

import numpy as np


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class PositionData:
    """Data structure for cell position information."""

    frames: np.ndarray
    position: dict[str, np.ndarray]  # {"x": array, "y": array}


@dataclass
class FeatureData:
    """Data structure for cell feature time series."""

    time_points: np.ndarray
    features: dict[
        str, np.ndarray
    ]  # {"feature_name1": array, "feature_name2": array, ...}
