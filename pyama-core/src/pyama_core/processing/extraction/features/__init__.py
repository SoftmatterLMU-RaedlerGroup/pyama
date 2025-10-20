"""Cell feature extraction algorithms and registry.

Features are discovered automatically from modules in this package.
Each feature module must define:
- FEATURE_TYPE: "phase" or "fluorescence"
- FEATURE_NAME: the feature identifier
- extract_{FEATURE_NAME}(): the extractor function
"""

from typing import Callable

from pyama_core.processing.extraction.features.context import ExtractionContext
from pyama_core.processing.extraction.features._plugins import discover_features

# =============================================================================
# FEATURE REGISTRATION (AUTO-DISCOVERED)
# =============================================================================
# Fluorescence-dependent features operate on intensity stacks per channel.
FLUORESCENCE_FEATURES: dict[str, Callable]

# Phase-contrast features operate on segmentation / masks derived from phase images.
PHASE_FEATURES: dict[str, Callable]

# Discover all registered features
FLUORESCENCE_FEATURES, PHASE_FEATURES = discover_features()

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
    "FLUORESCENCE_FEATURES",
    "PHASE_FEATURES",
    "FEATURE_EXTRACTORS",
    "list_features",
    "list_fluorescence_features",
    "list_phase_features",
    "get_feature_extractor",
    "discover_features",
]
