from typing import Callable

from .binarization import (
    logarithmic_std_binarization,
    global_otsu_binarization,
    cellpose_binarization,
)
from .background_correction import (
    schwarzfischer_background_correction,
    background_morphological_opening,
)

# Registries mapping human-friendly method keys to callables
BINARIZATION_ALGORITHMS: dict[str, Callable] = {
    "log-std": logarithmic_std_binarization,
    "global-otsu": global_otsu_binarization,
    "cellpose": cellpose_binarization,
}

BACKGROUND_CORRECTION_ALGORITHMS: dict[str, Callable] = {
    "schwarzfischer": schwarzfischer_background_correction,
    "morph-open": background_morphological_opening,
}


def get_binarization_algorithm(name: str) -> Callable:
    """Return a binarization algorithm by registry key.

    Raises KeyError if not found.
    """
    try:
        return BINARIZATION_ALGORITHMS[name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown binarization method '{name}'. Available: {list(BINARIZATION_ALGORITHMS.keys())}"
        ) from exc


def get_background_correction_algorithm(name: str) -> Callable:
    """Return a background correction algorithm by registry key.

    Raises KeyError if not found.
    """
    try:
        return BACKGROUND_CORRECTION_ALGORITHMS[name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown background correction method '{name}'. Available: {list(BACKGROUND_CORRECTION_ALGORITHMS.keys())}"
        ) from exc


__all__ = [
    "BINARIZATION_ALGORITHMS",
    "BACKGROUND_CORRECTION_ALGORITHMS",
    "get_binarization_algorithm",
    "get_background_correction_algorithm",
]


