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
from pathlib import Path
import logging
from pyama_qt.widgets.parameter_panel import ParameterPanel

logger = logging.getLogger(__name__)




class Workflow(QWidget):
    """Widget for configuring and controlling the processing workflow."""

    process_requested = Signal(dict)

    def __init__(self):
        super().__init__()
        self._source_info = None
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

    def set_data_available(self, available, info=None):
        self._source_info = info
        can_process = False
        if available and info:
            pc_channel = info.get("pc_channel")
            fl_channels = info.get("fl_channels") or []
            can_process = pc_channel is not None or len(fl_channels) > 0
        self.process_button.setEnabled(can_process)

    def select_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", "")
        if directory:
            self.save_dir.setText(directory)
            logger.info(f"Output directory selected: {directory}")

    def start_processing(self):
        if not self._source_info:
            return

        values = self.param_panel.get_values() or {}
        p = values.get("params", {}) or {}

        out_dir_str = self.save_dir.text().strip()
        context = {
            "output_dir": Path(out_dir_str) if out_dir_str else None,
            "channels": {
                "pc": int(self._source_info.get("pc_channel")) if self._source_info.get("pc_channel") is not None else 0,
                "fl": list(self._source_info.get("fl_channels", [])),
            },
            "npy_paths": {},
            "params": {},
        }

        params = {
            "fov_start": int(p.get("fov_start", 0)),
            "fov_end": int(p.get("fov_end", 0)),
            "batch_size": int(p.get("batch_size", 2)),
            "n_workers": int(p.get("n_workers", 2)),
        }

        try:
            if not out_dir_str:
                raise ValueError("Output directory is required")
            if params["fov_end"] < params["fov_start"]:
                raise ValueError("FOV End must be >= FOV Start")
            if params["batch_size"] <= 0 or params["n_workers"] <= 0:
                raise ValueError("Batch size and workers must be positive")
            if params["batch_size"] % params["n_workers"] != 0:
                raise ValueError("Batch size must be divisible by number of workers")
        except Exception as e:
            logger.error(str(e))
            return

        self.process_requested.emit({"context": context, "params": params})
        self.param_panel.setEnabled(False)
        self.process_button.setEnabled(False)
        logger.info("Starting complete workflow...")

    def update_progress(self, value, message=""):
        if message:
            logger.info(message)

    def processing_finished(self, success, message=""):
        self.param_panel.setEnabled(True)
        self.process_button.setEnabled(True)
        if success:
            logger.info("✓ Complete workflow finished successfully")
            if message:
                logger.info(message)
        else:
            logger.error(f"✗ Workflow failed: {message}")

    def processing_error(self, error_message):
        self.processing_finished(False, error_message)
