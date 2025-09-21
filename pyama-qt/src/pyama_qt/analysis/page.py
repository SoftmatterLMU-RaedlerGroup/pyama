"""Analysis tab composed of data, fitting, and results panels."""

import logging
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QStatusBar

from pyama_qt.analysis.controller import AnalysisController
from pyama_qt.analysis.panels import (
    AnalysisDataPanel,
    AnalysisFittingPanel,
    AnalysisResultsPanel,
)
from pyama_qt.analysis.state import AnalysisState, FittingRequest
from pyama_qt.ui import BasePage

logger = logging.getLogger(__name__)


class AnalysisPage(BasePage[AnalysisState]):
    """Embeddable analysis page comprising data, fitting, and results panels."""

    def __init__(self, parent=None):
        self.controller = AnalysisController()
        super().__init__(parent)
        self.set_state(self.controller.current_state())
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
        self.controller.state_changed.connect(self.set_state)
        self.controller.error_occurred.connect(self._show_error)
        self.controller.status_changed.connect(self._status_bar.showMessage)

        self.data_panel.csv_selected.connect(self.controller.load_csv)
        self.fitting_panel.fit_requested.connect(self._on_fit_requested)
        self.fitting_panel.cell_visualized.connect(self._highlight_cell_on_data_panel)

    def update_view(self) -> None:
        state = self.get_state()
        if state is None:
            return

        self.data_panel.set_state(state)
        self.fitting_panel.set_state(state)
        self.results_panel.set_state(state)

        if state.status_message:
            self._status_bar.showMessage(state.status_message)

    # Signal adapters ------------------------------------------------------
    def _on_fit_requested(self, request: FittingRequest) -> None:
        self.controller.start_fitting(request)

    def _highlight_cell_on_data_panel(self, cell_name: str) -> None:
        if not self.data_panel.highlight_cell(cell_name):
            logger.debug("Unable to highlight cell %s on data panel", cell_name)

    def _show_error(self, message: str) -> None:
        if message:
            QMessageBox.critical(self, "Analysis Error", message)
