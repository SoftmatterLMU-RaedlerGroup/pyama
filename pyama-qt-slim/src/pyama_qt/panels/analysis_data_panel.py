"""Data panel for loading CSV files and plotting traces."""

from PySide6.QtWidgets import (
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..components import MplCanvas


class AnalysisDataPanel(QWidget):
    """Left-side panel responsible for loading CSV data and visualisation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Data")
        group_layout = QVBoxLayout(group)

        self._load_button = QPushButton("Load CSV")
        group_layout.addWidget(self._load_button)

        self._canvas = MplCanvas(self, width=5, height=8)
        group_layout.addWidget(self._canvas)
        self._canvas.clear()

        layout.addWidget(group)
