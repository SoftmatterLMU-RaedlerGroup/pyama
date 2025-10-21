"""Analysis module components for data fitting and parameter analysis.

This module provides the main analysis tab and its sub-components for
loading trace data, performing model fitting, and analyzing parameter
distributions and fitting quality.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from pyama_pro.analysis.main_tab import AnalysisTab
from pyama_pro.analysis.data import DataPanel
from pyama_pro.analysis.parameter import ParameterPanel
from pyama_pro.analysis.quality import QualityPanel

__all__ = [
    "AnalysisTab",
    "DataPanel",
    "ParameterPanel",
    "QualityPanel",
]
