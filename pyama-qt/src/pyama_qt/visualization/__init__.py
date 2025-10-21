"""Visualization module components for displaying microscopy images and traces.

This module provides the main visualization tab and its sub-components for
loading, displaying, and interacting with microscopy images and trace data.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from pyama_qt.visualization.main_tab import VisualizationTab
from pyama_qt.visualization.image import ImagePanel
from pyama_qt.visualization.load import LoadPanel
from pyama_qt.visualization.trace import TracePanel

__all__ = [
    "VisualizationTab",
    "ImagePanel",
    "LoadPanel",
    "TracePanel",
]
