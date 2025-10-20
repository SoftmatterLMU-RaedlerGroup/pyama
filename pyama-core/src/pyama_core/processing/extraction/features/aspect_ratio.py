"""Aspect ratio feature - calculates the aspect ratio of the cell mask.

This is a fun example that shows how to extract shape properties from masks.
The aspect ratio is the ratio of the major axis to the minor axis of the cell.

To create your own feature:
1. Copy this file (e.g., cp _example_feature.py my_feature.py)
2. Update FEATURE_NAME to match your function name
3. Implement your extract_* function
4. It will be automatically discovered!
"""

import numpy as np

from pyama_core.processing.extraction.features.context import ExtractionContext

FEATURE_TYPE = "phase"  # Phase feature - operates on masks
FEATURE_NAME = "aspect_ratio"


def extract_aspect_ratio(ctx: ExtractionContext) -> np.float32:
    """
    Extract aspect ratio of the cell mask.

    Calculates the ratio of the major axis to the minor axis using
    the second moments of the mask.

    Returns:
        Aspect ratio (major_axis / minor_axis) as np.float32
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

