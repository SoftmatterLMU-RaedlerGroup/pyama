"""
Cell feature extraction algorithms.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class ExtractionContext:
    """Context containing all information needed for feature extraction."""
    fluor_frame: np.ndarray
    cell_mask: np.ndarray
    # Can be extended with more fields in the future, e.g.:
    # label_frame: np.ndarray
    # frame_index: int
    # pixel_size_um: float
    # etc.


def extract_intensity_total(ctx: ExtractionContext) -> float:
    """
    Extract total intensity for a single cell.
    
    Args:
        ctx: Extraction context containing fluor_frame and cell_mask
        
    Returns:
        Total fluorescence intensity (sum of pixel values)
    """
    cell_pixels = ctx.fluor_frame[ctx.cell_mask]
    return float(np.sum(cell_pixels))


def extract_area(ctx: ExtractionContext) -> int:
    """
    Extract area for a single cell.
    
    Args:
        ctx: Extraction context containing cell_mask
        
    Returns:
        Cell area in pixels
    """
    return int(np.sum(ctx.cell_mask))


# Feature extraction method mapping
FEATURE_EXTRACTORS = {
    "intensity_total": extract_intensity_total,
    "area": extract_area,
}


