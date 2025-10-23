"""Phase contrast feature: Cell circularity.

Measures how round a cell is (0-1, where 1 is perfectly circular).
Formula: 4π * Area / Perimeter²
"""

import numpy as np
from scipy import ndimage

PLUGIN_NAME = "circularity"
PLUGIN_TYPE = "feature"
PLUGIN_VERSION = "1.0.0"
PLUGIN_FEATURE_TYPE = "phase"


def extract_circularity(ctx) -> np.float32:
    """Extract circularity of a cell from its segmentation mask.

    Args:
        ctx: ExtractionContext with mask attribute (2D binary array)

    Returns:
        Circularity score (0-1, where 1 is perfectly circular)
    """
    mask = ctx.mask.astype(bool, copy=False)

    if not np.any(mask):
        return np.float32(0.0)

    area = float(np.sum(mask))
    struct = ndimage.generate_binary_structure(2, 1)
    dilated = ndimage.binary_dilation(mask, structure=struct)
    perimeter = float(np.sum(dilated & ~mask))

    if perimeter < 1.0:
        return np.float32(0.0)

    circularity = (4 * np.pi * area) / (perimeter ** 2)
    circularity = float(np.clip(circularity, 0.0, 1.0))

    return np.float32(circularity)
