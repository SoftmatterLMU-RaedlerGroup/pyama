"""Analysis page composed of data, fitting, and results panels."""

from PySide6.QtWidgets import QHBoxLayout, QStatusBar, QWidget

from ..panels import AnalysisDataPanel, AnalysisFittingPanel, AnalysisResultsPanel


class AnalysisPage(QWidget):
    """Analysis page comprising data, fitting, and results panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self._status_bar = QStatusBar(self)
        layout = QHBoxLayout(self)

        self.data_panel = AnalysisDataPanel(self)
        self.fitting_panel = AnalysisFittingPanel(self)
        self.results_panel = AnalysisResultsPanel(self)

        layout.addWidget(self.data_panel, 1)
        layout.addWidget(self.fitting_panel, 1)
        layout.addWidget(self.results_panel, 1)
        layout.addWidget(self._status_bar)
