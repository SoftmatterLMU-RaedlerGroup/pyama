"""Plugin system for automatic feature discovery."""

import importlib
import pkgutil
from typing import Callable


def discover_features() -> tuple[dict[str, Callable], dict[str, Callable]]:
    """Discover and register feature plugins from this package.

    Each feature module must have:
    - FEATURE_TYPE: "phase" or "fluorescence"
    - FEATURE_NAME: the feature identifier
    - extract_{FEATURE_NAME}(): the extractor function

    Returns:
        Tuple of (fluorescence_features, phase_features) dictionaries
    """
    fluorescence_features: dict[str, Callable] = {}
    phase_features: dict[str, Callable] = {}

    # Import all modules in this package
    import pyama_core.processing.extraction.features as features_pkg

    for importer, modname, ispkg in pkgutil.iter_modules(features_pkg.__path__):
        # Skip private modules and context
        if modname.startswith("_") or modname == "context":
            continue

        try:
            # Import the module
            module = importlib.import_module(
                f"pyama_core.processing.extraction.features.{modname}"
            )

            # Check for required metadata
            if not hasattr(module, "FEATURE_TYPE") or not hasattr(
                module, "FEATURE_NAME"
            ):
                continue

            feature_type = module.FEATURE_TYPE
            feature_name = module.FEATURE_NAME

            # Find the extractor function
            extractor_name = f"extract_{feature_name}"
            if not hasattr(module, extractor_name):
                continue

            extractor = getattr(module, extractor_name)

            # Register based on type
            if feature_type == "fluorescence":
                fluorescence_features[feature_name] = extractor
            elif feature_type == "phase":
                phase_features[feature_name] = extractor

        except Exception:
            # Skip modules that fail to import
            continue

    return fluorescence_features, phase_features

