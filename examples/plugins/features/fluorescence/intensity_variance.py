"""Fluorescence feature: Intensity variance within a cell.

Measures the heterogeneity of fluorescence signal within a cell.
Higher variance indicates more uneven distribution of the signal.
"""

import numpy as np

PLUGIN_NAME = "intensity_variance"
PLUGIN_TYPE = "feature"
PLUGIN_VERSION = "1.0.0"
PLUGIN_FEATURE_TYPE = "fluorescence"


def extract_intensity_variance(ctx) -> np.float32:
    """Extract intensity variance from within a cell region.

    Args:
        ctx: ExtractionContext with image and mask attributes
             image: 2D fluorescence intensity array
             mask: 2D binary mask of the cell

    Returns:
        Variance of pixel intensities within the cell region
    """
    mask = ctx.mask.astype(bool, copy=False)

    if not np.any(mask):
        return np.float32(0.0)

    pixel_values = ctx.image[mask].astype(np.float32)
    variance = float(np.var(pixel_values))

    return np.float32(variance)
