"""Legacy compatibility imports for analysis panels.

The refactor promotes the new :mod:`pyama_qt.analysis.panels` module.
"""

from pyama_qt.analysis.panels import AnalysisDataPanel, AnalysisFittingPanel, AnalysisResultsPanel

DataPanel = AnalysisDataPanel
FittingPanel = AnalysisFittingPanel
ResultsPanel = AnalysisResultsPanel

__all__ = [
    "DataPanel",
    "FittingPanel",
    "ResultsPanel",
    "AnalysisDataPanel",
    "AnalysisFittingPanel",
    "AnalysisResultsPanel",
]
