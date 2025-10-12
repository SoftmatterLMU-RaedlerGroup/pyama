"""Analysis tab composed of data, fitting, and results panels."""

from pathlib import Path

import pandas as pd
from PySide6.QtWidgets import QHBoxLayout, QStatusBar, QWidget

from .data import DataPanel
from .fitting import FittingPanel
from .results import ResultsPanel


class AnalysisTab(QWidget):
    """
    Embeddable analysis page comprising consolidated data, fitting, and results panels.
    This tab orchestrates the interactions between the panels.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()
        self._bind()

    def _build(self) -> None:
        layout = QHBoxLayout(self)

        self.data_panel = DataPanel(self)
        self.fitting_panel = FittingPanel(self)
        self.results_panel = ResultsPanel(self)

        layout.addWidget(self.data_panel, 1)
        layout.addWidget(self.fitting_panel, 1)
        layout.addWidget(self.results_panel, 1)

        # The status bar can be part of the main window, but for now, let's let a panel manage it.
        # If a central status bar is needed, we can emit a signal from the panels.

    def _bind(self) -> None:
        """
        Wire up the signals and slots between the panels to create the application logic.
        """
        # --- Data Panel -> Fitting Panel ---
        # When new data is loaded, notify the fitting panel
        self.data_panel.rawDataChanged.connect(self.fitting_panel.on_raw_data_changed)
        self.data_panel.rawCsvPathChanged.connect(self.fitting_panel.on_raw_csv_path_changed)

        # --- Fitting Panel -> Data Panel ---
        # Allow fitting panel to request a random cell for visualization
        self.fitting_panel.shuffle_requested.connect(
            lambda: self.fitting_panel.on_shuffle_requested(self.data_panel.get_random_cell)
        )
        # When a cell is visualized in the fitting panel, highlight it in the data panel
        self.fitting_panel.cell_visualized.connect(self.data_panel.highlight_cell)


        # --- Fitting Panel -> Results Panel ---
        # When fitting is complete, send the results to the results panel
        self.fitting_panel.fittingCompleted.connect(self.results_panel.on_fitting_completed)
        # Forward status messages to a status bar (if one existed on this tab)
        # self.fitting_panel.statusMessage.connect(self.status_bar.showMessage)


        # --- Results Panel -> Fitting Panel ---
        # When fitted results are loaded from a file, notify the fitting panel
        # so it can display the fit curve on the QC plot.
        self.results_panel.saveRequested.connect(self._handle_load_fitted_results)


    def _handle_load_fitted_results(self, path: Path) -> None:
        """
        A helper to connect the results panel's loading of external data
        back to the fitting panel for visualization.
        """
        # This is a bit of a workaround. The ResultsPanel loads the data,
        # then we need to tell the FittingPanel about it.
        try:
            df = pd.read_csv(path)
            self.fitting_panel.on_fitted_results_changed(df)
        except Exception:
            # The results panel will log the error, so we don't need to do it again here.
            pass