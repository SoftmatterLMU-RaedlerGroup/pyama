"""Image panel for displaying microscopy images."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ....components.ui.canvas import Canvas


class ImagePanel(QWidget):
    """Panel for displaying and interacting with microscopy images."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Image group
        image_group = QGroupBox("Image Viewer")
        image_layout = QVBoxLayout(image_group)

        # Controls layout
        controls_layout = QHBoxLayout()

        # Data type selection
        controls_layout.addWidget(QLabel("Data Type:"))
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["Raw", "Segmentation", "Tracking"])
        controls_layout.addWidget(self.data_type_combo)

        # Frame navigation
        self.prev_frame_10_button = QPushButton("<<")
        controls_layout.addWidget(self.prev_frame_10_button)

        self.prev_frame_button = QPushButton("<")
        controls_layout.addWidget(self.prev_frame_button)

        # Frame label
        self.frame_label = QLabel("Frame 0/0")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(self.frame_label)

        self.next_frame_button = QPushButton(">")
        controls_layout.addWidget(self.next_frame_button)

        self.next_frame_10_button = QPushButton(">>")
        controls_layout.addWidget(self.next_frame_10_button)

        image_layout.addLayout(controls_layout)

        # Image display
        self.canvas = Canvas(self, width=8, height=6, dpi=100)
        image_layout.addWidget(self.canvas, 1)

        layout.addWidget(image_group)
