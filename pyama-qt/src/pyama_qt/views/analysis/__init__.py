"""Analysis views for the PyAMA-Qt application."""

from .data_panel import AnalysisDataPanel
from .fitting_panel import AnalysisFittingPanel
from .page import AnalysisPage
from .results_panel import AnalysisResultsPanel

__all__ = [
    "AnalysisDataPanel",
    "AnalysisFittingPanel",
    "AnalysisPage",
    "AnalysisResultsPanel",
]
