"""Total intensity feature extraction."""

import numpy as np
from scipy.ndimage import binary_erosion

from pyama_core.types.processing import ExtractionContext


def extract_intensity_total(ctx: ExtractionContext) -> np.float32:
    """
    Extract total intensity for a single cell.

    Computes background-corrected intensity as (image - weight * background).
    Background is always present in context (zeros if no correction available).
    Optionally erodes the mask before summing to exclude edge pixels.

    Args:
        ctx: Extraction context containing image, mask, background, background_weight, and erosion_size

    Returns:
        Background-corrected total fluorescence intensity (fl - weight * fl_background)
        as np.float32. Returns 0.0 if mask becomes empty after erosion.
    """
    image = ctx.image.astype(np.float32, copy=False)
    background = ctx.background.astype(np.float32, copy=False)
    mask = ctx.mask.astype(bool, copy=False)
    weight = float(ctx.background_weight)
    erosion_size = int(ctx.erosion_size)
    
    # Apply erosion to mask if requested (only for intensity_total)
    if erosion_size > 0:
        erosion_struct = np.ones((erosion_size, erosion_size), dtype=bool)
        mask = binary_erosion(mask, structure=erosion_struct)
        # Return 0 if mask becomes empty after erosion
        if not mask.any():
            return np.float32(0.0)
    
    corrected_image = image - weight * background
    return corrected_image[mask].sum()
