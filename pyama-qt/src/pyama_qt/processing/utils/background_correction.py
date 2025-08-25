'''
Background correction algorithms for fluorescence microscopy image analysis.

This module is a wrapper around the implementation in pyama_core.
'''

from pyama_core.processing.background_correction import (
    schwarzfischer_background_correction,
    background_morphological_opening,
)

__all__ = [
    "schwarzfischer_background_correction",
    "background_morphological_opening",
]