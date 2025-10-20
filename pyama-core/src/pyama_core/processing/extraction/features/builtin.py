"""
Cell feature extraction algorithms.
"""

from dataclasses import dataclass
from typing import Callable

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


# =============================================================================
# FEATURE REGISTRATION
# =============================================================================
# Fluorescence-dependent features operate on intensity stacks per channel.
FLUORESCENCE_FEATURES: dict[str, Callable] = {
    "intensity_total": extract_intensity_total,
}

# Phase-contrast features operate on segmentation / masks derived from phase images.
PHASE_FEATURES: dict[str, Callable] = {
    "area": extract_area,
}

# Flattened lookup used by the extraction pipeline.
FEATURE_EXTRACTORS: dict[str, Callable] = {
    **FLUORESCENCE_FEATURES,
    **PHASE_FEATURES,
}


def list_features() -> list[str]:
    """Return all registered feature names."""
    return list(FEATURE_EXTRACTORS.keys())


def list_fluorescence_features() -> list[str]:
    """Return fluorescence-dependent features."""
    return list(FLUORESCENCE_FEATURES.keys())


def list_phase_features() -> list[str]:
    """Return phase-contrast features."""
    return list(PHASE_FEATURES.keys())


def get_feature_extractor(feature_name: str):
    return FEATURE_EXTRACTORS[feature_name]
