"""Cell area feature extraction."""

import numpy as np

from pyama_core.processing.extraction.features.context import ExtractionContext


def extract_area(ctx: ExtractionContext) -> np.int32:
    """
    Extract area for a single cell.

    Args:
        ctx: Extraction context containing mask

    Returns:
        Cell area in pixels as np.int32
    """
    mask = ctx.mask.astype(bool, copy=False)
    return np.sum(mask)

