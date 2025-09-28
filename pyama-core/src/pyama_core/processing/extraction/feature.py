"""
Cell feature extraction algorithms.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class ExtractionContext:
    """Context containing all information needed for feature extraction."""

    image: np.ndarray
    mask: np.ndarray
    # background: np.ndarray


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


# Feature extraction method mapping
FEATURE_EXTRACTORS = {
    "intensity_total": extract_intensity_total,
    "area": extract_area,
}


def list_features():
    return list(FEATURE_EXTRACTORS.keys())


def get_feature_extractor(feature_name: str):
    return FEATURE_EXTRACTORS[feature_name]
