"""Cell feature extraction algorithms and registry.

Features are explicitly registered from modules in this package.
Each feature module must define an extract_* function.
"""

from collections.abc import Callable

from pyama_core.processing.extraction.features import area
from pyama_core.processing.extraction.features import aspect_ratio
from pyama_core.processing.extraction.features import intensity_total
from pyama_core.processing.extraction.features.context import ExtractionContext

# =============================================================================
# FEATURE REGISTRATION (EXPLICIT)
# =============================================================================
# Phase-contrast features operate on segmentation / masks derived from phase images.
PHASE_FEATURES: dict[str, Callable] = {}

# Register phase contrast features
PHASE_FEATURES["area"] = area.extract_area
PHASE_FEATURES["aspect_ratio"] = aspect_ratio.extract_aspect_ratio

# Fluorescence-dependent features operate on intensity stacks per channel.
FLUORESCENCE_FEATURES: dict[str, Callable] = {}

# Register fluorescence features
FLUORESCENCE_FEATURES["intensity_total"] = intensity_total.extract_intensity_total

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


def register_plugin_feature(
    feature_name: str,
    extractor: Callable,
    feature_type: str
) -> None:
    """Register a plugin feature at runtime.

    Args:
        feature_name: Name of the feature (e.g., "my_feature")
        extractor: Callable that takes ExtractionContext and returns float
        feature_type: "phase" or "fluorescence"

    Raises:
        ValueError: If feature_type is invalid or feature_name already registered
    """
    if feature_type not in ("phase", "fluorescence"):
        raise ValueError(f"Invalid feature_type: {feature_type}")

    if feature_name in FEATURE_EXTRACTORS:
        raise ValueError(
            f"Feature '{feature_name}' is already registered. "
            f"Plugin features must have unique names."
        )

    if feature_type == "phase":
        PHASE_FEATURES[feature_name] = extractor
    else:  # fluorescence
        FLUORESCENCE_FEATURES[feature_name] = extractor

    # Update the unified lookup
    FEATURE_EXTRACTORS[feature_name] = extractor


__all__ = [
    "ExtractionContext",
    "FLUORESCENCE_FEATURES",
    "PHASE_FEATURES",
    "FEATURE_EXTRACTORS",
    "list_features",
    "list_fluorescence_features",
    "list_phase_features",
    "get_feature_extractor",
    "register_plugin_feature",
]
