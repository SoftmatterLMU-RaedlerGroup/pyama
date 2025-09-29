"""Results panel for displaying fitting results and statistics."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..components import MplCanvas


class AnalysisResultsPanel(QWidget):
    """Right-side panel for displaying fitting results and plots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._results_group = self._build_results_group()
        layout.addWidget(self._results_group)

    def _build_results_group(self) -> QGroupBox:
        group = QGroupBox("Results")
        layout = QVBoxLayout(group)

        layout.addWidget(QLabel("Fitting Quality"))
        self._quality_canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self._quality_canvas)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Parameter:"))
        self._param_combo = QComboBox()
        controls.addWidget(self._param_combo)

        controls.addStretch()
        self._filter_checkbox = QCheckBox("Good Fits Only")
        controls.addWidget(self._filter_checkbox)

        self._save_button = QPushButton("Save Plot")
        controls.addWidget(self._save_button)

        layout.addLayout(controls)

        self._param_canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self._param_canvas)

        return group
