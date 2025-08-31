'''
Workflow widget for PyAMA-Qt processing application.
'''

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QLineEdit,
    QFileDialog,
    QFormLayout,
)
from PySide6.QtCore import Signal
from dataclasses import dataclass

from pyama_qt.utils.logging_config import get_logger
from pyama_qt.widgets.parameter_panel import ParameterPanel


@dataclass(slots=True)
class ProcessingParams:
    """View-model for processing parameter collection and validation."""
    output_dir: str
    data_info: dict
    fov_start: int
    fov_end: int
    batch_size: int
    n_workers: int

    def as_dict(self) -> dict:
        return {
            "data_info": self.data_info,
            "output_dir": self.output_dir,
            "base_name": self.data_info["filename"].split(".")[0],
            "enabled_steps": [
                "segmentation",
                "background_correction",
                "tracking",
                "bounding_box",
            ],
            "fov_start": self.fov_start,
            "fov_end": self.fov_end,
            "batch_size": self.batch_size,
            "n_workers": self.n_workers,
            "min_trace_length": 20,
        }

    def validate(self) -> None:
        if not self.output_dir:
            raise ValueError("Output directory is required")
        if self.fov_end < self.fov_start:
            raise ValueError("FOV End must be >= FOV Start")
        if self.batch_size <= 0 or self.n_workers <= 0:
            raise ValueError("Batch size and workers must be positive")
        if self.batch_size % self.n_workers != 0:
            raise ValueError("Batch size must be divisible by number of workers")


class Workflow(QWidget):
    """Widget for configuring and controlling the processing workflow."""

    process_requested = Signal(dict)

    def __init__(self):
        super().__init__()
        self.data_info = None
        self.logger = get_logger(__name__)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)

        self.setup_output_section(layout)
        self.setup_processing_section(layout)

        layout.addStretch()

    def setup_output_section(self, layout):
        output_group = QGroupBox("Output")
        output_layout = QFormLayout(output_group)
        dir_header_layout = QHBoxLayout()
        dir_label = QLabel("Save Directory:")
        self.dir_button = QPushButton("Browse...")
        self.dir_button.clicked.connect(self.select_output_directory)
        dir_header_layout.addWidget(dir_label)
        dir_header_layout.addStretch()
        dir_header_layout.addWidget(self.dir_button)
        self.save_dir = QLineEdit("")
        self.save_dir.setReadOnly(True)
        output_layout.addRow(dir_header_layout)
        output_layout.addRow(self.save_dir)
        layout.addWidget(output_group)

    def setup_processing_section(self, layout):
        process_group = QGroupBox("Processing Settings")
        process_layout = QVBoxLayout(process_group)

        self.param_panel = ParameterPanel()
        # Arrange processing parameters in a 2x2 grid
        self.param_panel.set_columns(2)
        param_definitions = [
            {"name": "fov_start", "label": "FOV Start", "type": "int", "default": 0, "min": 0, "max": 99999},
            {"name": "fov_end", "label": "FOV End", "type": "int", "default": 0, "min": 0, "max": 99999},
            {"name": "batch_size", "label": "Batch Size", "type": "int", "default": 2, "min": 1, "max": 100},
            {"name": "n_workers", "label": "Workers", "type": "int", "default": 2, "min": 1, "max": 32},
        ]
        self.param_panel.set_parameters(param_definitions)
        process_layout.addWidget(self.param_panel)

        self.process_button = QPushButton("Start Complete Workflow")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.start_processing)
        process_layout.addWidget(self.process_button)

        layout.addWidget(process_group)

    def set_data_available(self, available, data_info=None):
        self.data_info = data_info
        can_process = False
        if available and data_info:
            pc_channel = data_info.get("pc_channel")
            fl_channel = data_info.get("fl_channel")
            can_process = pc_channel is not None or fl_channel is not None
        self.process_button.setEnabled(can_process)

    def select_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", "")
        if directory:
            self.save_dir.setText(directory)
            self.logger.info(f"Output directory selected: {directory}")

    def start_processing(self):
        if not self.data_info:
            return

        params = self.param_panel.get_values()
        vm = ProcessingParams(
            output_dir=self.save_dir.text().strip(),
            data_info=self.data_info,
            **params
        )

        try:
            vm.validate()
        except Exception as e:
            self.logger.error(str(e))
            return

        self.process_requested.emit(vm.as_dict())
        self.param_panel.setEnabled(False)
        self.process_button.setEnabled(False)
        self.logger.info(f"Starting complete workflow...")

    def update_progress(self, value, message=""):
        if message:
            self.logger.info(message)

    def processing_finished(self, success, message=""):
        self.param_panel.setEnabled(True)
        self.process_button.setEnabled(True)
        if success:
            self.logger.info("✓ Complete workflow finished successfully")
            if message:
                self.logger.info(message)
        else:
            self.logger.error(f"✗ Workflow failed: {message}")

    def processing_error(self, error_message):
        self.processing_finished(False, error_message)
