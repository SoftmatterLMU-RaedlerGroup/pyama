"""Total intensity feature extraction."""

import numpy as np

from pyama_core.processing.extraction.features.context import ExtractionContext


def extract_intensity_total(ctx: ExtractionContext) -> np.float32:
    """
    Extract total intensity for a single cell.

    Computes background-corrected intensity as (image - weight * background).
    Background is always present in context (zeros if no correction available).

    Args:
        ctx: Extraction context containing image, mask, background, and background_weight

    Returns:
        Background-corrected total fluorescence intensity (fl - weight * fl_background)
        as np.float32.
    """
    image = ctx.image.astype(np.float32, copy=False)
    background = ctx.background.astype(np.float32, copy=False)
    mask = ctx.mask.astype(bool, copy=False)
    weight = float(ctx.background_weight)
    
    corrected_image = image - weight * background
    return corrected_image[mask].sum()
