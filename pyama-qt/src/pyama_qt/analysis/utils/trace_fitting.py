'''
Utilities for fitting trace data from DataFrames.

This module is a wrapper around the implementation in pyama_core.
'''

from pyama_core.analysis.fitting import (
    fit_trace_data,
    get_trace,
)

__all__ = [
    "fit_trace_data",
    "get_trace",
]
