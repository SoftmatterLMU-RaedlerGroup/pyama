"""Trace panel for displaying and analyzing traces."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ..components import MplCanvas


class TracePanel(QWidget):
    """Panel for displaying and analyzing individual traces."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        plot_group = QGroupBox("Traces")
        plot_vbox = QVBoxLayout(plot_group)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Feature:"))
        self._feature_dropdown = QComboBox()
        self._feature_dropdown.addItems(["Area", "Intensity", "Perimeter", "Circularity"])
        selector_layout.addWidget(self._feature_dropdown, 1)
        selector_layout.addStretch()
        plot_vbox.addLayout(selector_layout)

        self._canvas = MplCanvas(self, width=8, height=6, dpi=100)
        plot_vbox.addWidget(self._canvas)
        layout.addWidget(plot_group, 1)

        list_group = QGroupBox("Trace Selection")
        list_vbox = QVBoxLayout(list_group)

        # Pagination controls
        pagination_layout = QHBoxLayout()
        self._prev_button = QPushButton("Previous")
        pagination_layout.addWidget(self._prev_button, 1)

        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addWidget(self._page_label, 1)

        self._next_button = QPushButton("Next")
        pagination_layout.addWidget(self._next_button, 1)

        list_vbox.addLayout(pagination_layout)

        # Control buttons
        button_layout = QHBoxLayout()
        self._check_all_button = QPushButton("Check All")
        button_layout.addWidget(self._check_all_button, 1)

        self._uncheck_all_button = QPushButton("Uncheck All")
        button_layout.addWidget(self._uncheck_all_button, 1)

        self._invert_selection_button = QPushButton("Invert Selection")
        button_layout.addWidget(self._invert_selection_button, 1)

        list_vbox.addLayout(button_layout)

        # Trace table placeholder
        self._trace_table_placeholder = QGroupBox("Trace Table")
        list_vbox.addWidget(self._trace_table_placeholder)

        layout.addWidget(list_group, 1)
