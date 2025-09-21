"""Legacy compatibility imports for processing widgets.

The refactor promotes the new :mod:`pyama_qt.processing.panels` module. Import
from there for new code.
"""

from pyama_qt.processing.panels import ProcessingConfigPanel, ProcessingMergePanel

WorkflowPanel = ProcessingConfigPanel
MergePanel = ProcessingMergePanel

__all__ = [
    "WorkflowPanel",
    "MergePanel",
    "ProcessingConfigPanel",
    "ProcessingMergePanel",
]
