"""Analysis tab composed of data, fitting, and results panels."""

import logging

from PySide6.QtWidgets import QHBoxLayout, QStatusBar

from .controller import AnalysisController
from pyama_qt.analysis.panels import (
    AnalysisDataPanel,
    AnalysisFittingPanel,
    AnalysisResultsPanel,
)
from pyama_qt.ui import ModelBoundPage

logger = logging.getLogger(__name__)


class AnalysisPage(ModelBoundPage):
    """Embeddable analysis page comprising data, fitting, and results panels."""

    def __init__(self, parent=None):
        self.controller = AnalysisController()
        super().__init__(parent)
        logger.info("PyAMA Analysis Page loaded")

    # BasePage hooks -------------------------------------------------------
    def build(self) -> None:
        self._status_bar = QStatusBar(self)
        layout = QHBoxLayout(self)

        self.data_panel = AnalysisDataPanel(self)
        self.fitting_panel = AnalysisFittingPanel(self)
        self.results_panel = AnalysisResultsPanel(self)

        layout.addWidget(self.data_panel, 1)
        layout.addWidget(self.fitting_panel, 1)
        layout.addWidget(self.results_panel, 1)
        layout.addWidget(self._status_bar)

    def bind(self) -> None:
        self._bind_models()

        self.data_panel.csv_selected.connect(self.controller.load_csv)
        self.fitting_panel.fit_requested.connect(self.controller.start_fitting)
        self.data_panel.highlight_requested.connect(self.controller.highlight_cell)
        self.data_panel.random_cell_requested.connect(
            lambda: self.controller.highlight_cell(
                self.controller.get_random_cell() or ""
            )
        )
        self.fitting_panel.cell_visualized.connect(self.controller.highlight_cell)

        self.controller.fitting_model.statusMessageChanged.connect(
            self._status_bar.showMessage
        )

    def _bind_models(self) -> None:
        self.data_panel.set_models(self.controller.data_model)
        self.fitting_panel.set_models(
            self.controller.data_model,
            self.controller.fitting_model,
            self.controller.results_model,
        )
        self.results_panel.set_models(self.controller.results_model)

    # Signal adapters ------------------------------------------------------
    def _show_error(self, message: str) -> None:
        if message:
            logger.error(f"Analysis Error: {message}")
