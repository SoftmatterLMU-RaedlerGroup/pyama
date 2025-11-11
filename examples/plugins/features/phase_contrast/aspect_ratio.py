"""Phase contrast feature: Cell aspect ratio.

Measures the elongation of a cell by calculating the ratio of the major axis
to the minor axis using the second moments of the mask.
Aspect ratio of 1.0 indicates a perfectly round cell, higher values indicate elongation.
"""

import numpy as np

PLUGIN_NAME = "aspect_ratio"
PLUGIN_TYPE = "feature"
PLUGIN_VERSION = "1.0.0"
PLUGIN_FEATURE_TYPE = "phase"


def extract_aspect_ratio(ctx) -> np.float32:
    """Extract aspect ratio of a cell from its segmentation mask.

    Calculates the ratio of the major axis to the minor axis using
    the second moments of the mask.

    Args:
        ctx: ExtractionContext with mask attribute (2D binary array)

    Returns:
        Aspect ratio (major_axis / minor_axis) as np.float32.
        Returns 1.0 for empty masks or when minor_axis is 0.
    """
    mask = ctx.mask.astype(bool, copy=False)

    # Get the coordinates of the mask
    coords = np.argwhere(mask)
    if len(coords) == 0:
        return np.float32(1.0)

    # Calculate covariance matrix
    cov = np.cov(coords.T)

    # Get eigenvalues (squared axis lengths)
    eigenvalues = np.linalg.eigvalsh(cov)
    eigenvalues = np.sqrt(eigenvalues)

    # Aspect ratio is the ratio of major to minor axis
    major_axis = np.max(eigenvalues)
    minor_axis = np.min(eigenvalues)

    if minor_axis == 0:
        return np.float32(1.0)

    aspect_ratio = major_axis / minor_axis
    return np.float32(aspect_ratio)
