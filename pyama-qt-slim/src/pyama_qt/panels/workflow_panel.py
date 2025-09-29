"""Workflow panel for managing processing workflows."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class WorkflowPanel(QWidget):
    """Panel for managing and executing processing workflows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)

        self._input_group = self._build_input_group()
        self._output_group = self._build_output_group()

        layout.addWidget(self._input_group, 1)
        layout.addWidget(self._output_group, 1)

    def _build_input_group(self) -> QGroupBox:
        group = QGroupBox("Input")
        layout = QVBoxLayout(group)

        header = QHBoxLayout()
        header.addWidget(QLabel("Microscopy File:"))
        header.addStretch()
        self._nd2_button = QPushButton("Browse")
        header.addWidget(self._nd2_button)
        layout.addLayout(header)

        self._microscopy_path_field = QLineEdit()
        self._microscopy_path_field.setReadOnly(True)
        self._microscopy_path_field.setText("/path/to/microscopy/file.nd2")
        layout.addWidget(self._microscopy_path_field)

        self._channel_container = self._build_channel_section()
        layout.addWidget(self._channel_container)

        return group

    def _build_channel_section(self) -> QGroupBox:
        group = QGroupBox("Channels")
        layout = QVBoxLayout(group)

        pc_layout = QVBoxLayout()
        pc_layout.addWidget(QLabel("Phase Contrast"))
        self._pc_combo = QComboBox()
        self._pc_combo.addItem("None", None)
        pc_layout.addWidget(self._pc_combo)
        layout.addLayout(pc_layout)

        fl_layout = QVBoxLayout()
        fl_layout.addWidget(QLabel("Fluorescence (multi-select)"))
        self._fl_list = QListWidget()
        # Configure for multi-selection without needing modifier keys
        self._fl_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._fl_list.setSelectionBehavior(QListWidget.SelectionBehavior.SelectItems)
        self._fl_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Keep the widget interactive by default; avoid explicit enable/disable calls.
        self._fl_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._fl_list.setMouseTracking(True)

        # Add mock fluorescence channels
        mock_channels = ["GFP", "RFP", "DAPI", "Cy5", "FITC"]
        for channel in mock_channels:
            self._fl_list.addItem(channel)

        fl_layout.addWidget(self._fl_list)
        layout.addLayout(fl_layout)

        return group

    def _create_parameter_panel(self) -> QGroupBox:
        """Create parameter panel with mock data."""
        group = QGroupBox("Parameters")
        layout = QVBoxLayout(group)

        # Create table widget
        self.param_table = QTableWidget()
        self.param_table.setColumnCount(2)
        self.param_table.setHorizontalHeaderLabels(["Parameter", "Value"])

        # Mock parameter data
        mock_params = [
            ["FOV Start", "1"],
            ["FOV End", "50"],
            ["Batch Size", "2"],
            ["Workers", "2"],
        ]

        self.param_table.setRowCount(len(mock_params))
        for row, (param_name, value) in enumerate(mock_params):
            self.param_table.setItem(row, 0, QTableWidgetItem(param_name))
            self.param_table.setItem(row, 1, QTableWidgetItem(value))

        # Make table read-only for UI-only implementation
        self.param_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        layout.addWidget(self.param_table)
        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)

        header = QHBoxLayout()
        header.addWidget(QLabel("Save Directory:"))
        header.addStretch()
        self._output_button = QPushButton("Browse")
        header.addWidget(self._output_button)
        layout.addLayout(header)

        self._output_dir_field = QLineEdit()
        self._output_dir_field.setReadOnly(True)
        self._output_dir_field.setText("/path/to/output/directory/")
        layout.addWidget(self._output_dir_field)

        # Parameter panel with mock data
        self._param_panel = self._create_parameter_panel()
        layout.addWidget(self._param_panel)

        self._process_button = QPushButton("Start Complete Workflow")
        layout.addWidget(self._process_button)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        return group
