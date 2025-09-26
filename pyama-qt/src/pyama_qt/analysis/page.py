"""Analysis tab composed of data, fitting, and results panels."""

import logging
import dataclasses
from typing import Any

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
        self._last_state: AnalysisState | None = None
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
        self.data_panel.plot_requested.connect(
            lambda: self.controller.load_csv(
                self.data_panel.csv_path
                if hasattr(self.data_panel, "csv_path")
                else None
            )
        )
        self.data_panel.highlight_requested.connect(self.controller.highlight_cell)
        self.data_panel.random_cell_requested.connect(
            lambda: self.controller.highlight_cell(
                self.controller.get_random_cell() or ""
            )
        )

    def update_view(self) -> None:
        state = self.get_state()
        if state is None:
            self._last_state = None
            return

        changes = self._diff_states(self._last_state, state)

        if "raw_data" in changes or "plot_data" in changes:
            self.data_panel.set_state(state)
        if "fitted_results" in changes:
            self.results_panel.set_state(state)
        if "fitting_params" in changes:  # Assume field
            self.fitting_panel.set_state(state)

        self._last_state = state

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

    @staticmethod
    def _diff_states(old: AnalysisState | None, new: AnalysisState) -> dict[str, Any]:
        if old is None:
            return dataclasses.asdict(new)
        old_dict = dataclasses.asdict(old)
        new_dict = dataclasses.asdict(new)
        return {k: new_dict[k] for k in new_dict if old_dict.get(k) != new_dict[k]}
