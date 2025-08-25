'''
Simplified fitting utilities for trace data analysis.

This module is a wrapper around the implementation in pyama_core.
'''

from pyama_core.analysis.fitting import (
    fit_model,
    FittingResult,
)

__all__ = [
    "fit_model",
    "FittingResult",
]