'''
Module for parsing and organizing trace data from CSV files.

This module is a wrapper around the implementation in pyama_core.
'''

from pyama_core.io.trace_parser import (
    TraceParser,
    TraceData,
    FeatureData,
    PositionData,
)

__all__ = [
    "TraceParser",
    "TraceData",
    "FeatureData",
    "PositionData",
]