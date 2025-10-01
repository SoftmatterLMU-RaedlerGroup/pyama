"""Project panel for managing analysis projects."""

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ProjectPanel(QWidget):
    """Panel for managing analysis projects and datasets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Project loading section
        load_group = QGroupBox("Load Data Folder")
        load_layout = QVBoxLayout(load_group)

        self.load_button = QPushButton("Load Folder")
        load_layout.addWidget(self.load_button)

        # Project details text area
        self.project_details_text = QTextEdit()
        self.project_details_text.setReadOnly(True)
        self.project_details_text.setText(
            "Project: Sample Dataset\nFOVs: 1-50\nChannels: GFP, RFP, DAPI\nStatus: Loaded"
        )
        load_layout.addWidget(self.project_details_text)

        layout.addWidget(load_group, 1)

        # Selection controls
        selection_group = QGroupBox("Visualization Settings")
        selection_layout = QVBoxLayout(selection_group)

        # FOV selection
        fov_row = QHBoxLayout()
        self.fov_spinbox = QSpinBox()
        self.fov_spinbox.setMinimum(0)
        self.fov_spinbox.setMaximum(999)

        self.fov_max_label = QLabel("/ 0")
        self.fov_max_label.setStyleSheet("color: gray;")

        fov_row.addWidget(QLabel("FOV:"))
        fov_row.addStretch()
        fov_row.addWidget(self.fov_spinbox)
        fov_row.addWidget(self.fov_max_label)

        selection_layout.addLayout(fov_row)

        # Channel selection section
        channels_label = QLabel("Channels to load:")
        channels_label.setStyleSheet("font-weight: bold;")
        selection_layout.addWidget(channels_label)

        # Placeholder for channel list
        self.channels_placeholder = QGroupBox("Channels")
        selection_layout.addWidget(self.channels_placeholder)

        layout.addWidget(selection_group, 1)
