"""Processing module components for workflow and merge functionality.

This module provides the main processing tab and its sub-components for
configuring and running the image processing workflow and merging results.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from pyama_pro.processing.main_tab import ProcessingTab
from pyama_pro.processing.merge import MergePanel
from pyama_pro.processing.workflow import WorkflowPanel

__all__ = [
    "ProcessingTab",
    "MergePanel",
    "WorkflowPanel",
]
