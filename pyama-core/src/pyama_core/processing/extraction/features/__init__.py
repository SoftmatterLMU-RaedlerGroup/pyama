"""Cell feature extraction algorithms and registry."""

from typing import Callable

from pyama_core.processing.extraction.features.area import extract_area
from pyama_core.processing.extraction.features.context import ExtractionContext
from pyama_core.processing.extraction.features.intensity_total import (
    extract_intensity_total,
)

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
    """Get the feature extractor function for a given feature name."""
    return FEATURE_EXTRACTORS[feature_name]


__all__ = [
    "ExtractionContext",
    "extract_area",
    "extract_intensity_total",
    "FLUORESCENCE_FEATURES",
    "PHASE_FEATURES",
    "FEATURE_EXTRACTORS",
    "list_features",
    "list_fluorescence_features",
    "list_phase_features",
    "get_feature_extractor",
]
