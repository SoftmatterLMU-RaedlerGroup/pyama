"""Total intensity feature extraction."""

import numpy as np

from pyama_core.processing.extraction.features.context import ExtractionContext

# Feature type metadata for automatic discovery
FEATURE_TYPE = "fluorescence"
FEATURE_NAME = "intensity_total"


def extract_intensity_total(ctx: ExtractionContext) -> np.float32:
    """
    Extract total intensity for a single cell.

    Args:
        ctx: Extraction context containing image and mask

    Returns:
        Total fluorescence intensity (sum of pixel values) as np.float32
    """
    image = ctx.image.astype(np.float32, copy=False)
    mask = ctx.mask.astype(bool, copy=False)
    return image[mask].sum()

