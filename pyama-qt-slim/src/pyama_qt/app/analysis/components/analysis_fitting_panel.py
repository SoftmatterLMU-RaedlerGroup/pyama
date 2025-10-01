"""Fitting panel for model selection and parameter configuration."""

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ....components.ui.canvas import Canvas


class AnalysisFittingPanel(QWidget):
    """Middle panel for fitting model selection and parameters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._fitting_group = self._build_fitting_group()
        self._qc_group = self._build_qc_group()

        layout.addWidget(self._fitting_group, 1)
        layout.addWidget(self._qc_group, 1)

    def _build_fitting_group(self) -> QGroupBox:
        group = QGroupBox("Fitting")
        group_layout = QVBoxLayout(group)

        form = QFormLayout()
        self._model_combo = QComboBox()
        self._model_combo.addItems(["Trivial", "Maturation"])
        form.addRow("Model:", self._model_combo)
        group_layout.addLayout(form)

        # Parameter panel placeholder (would be ParameterPanel in real implementation)
        self._param_placeholder = QGroupBox("Parameters")
        group_layout.addWidget(self._param_placeholder)

        self._start_button = QPushButton("Start Fitting")
        group_layout.addWidget(self._start_button)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        group_layout.addWidget(self._progress_bar)

        return group

    def _build_qc_group(self) -> QGroupBox:
        group = QGroupBox("Quality Check")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        self._cell_input = QLineEdit()
        self._cell_input.setPlaceholderText("Enter cell ID (column name)")
        row.addWidget(self._cell_input)

        self._visualize_button = QPushButton("Visualize")
        row.addWidget(self._visualize_button)

        self._shuffle_button = QPushButton("Shuffle")
        row.addWidget(self._shuffle_button)
        layout.addLayout(row)

        self._qc_canvas = Canvas(self, width=5, height=3)
        layout.addWidget(self._qc_canvas)

        return group
