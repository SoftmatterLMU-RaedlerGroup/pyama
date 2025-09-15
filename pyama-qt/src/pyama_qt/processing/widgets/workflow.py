"""
Unified WorkflowPanel widget for PyAMA-Qt processing application.

This merges the file loading/channel assignment UI and the processing workflow
configuration into a single widget.
"""

from pathlib import Path
import logging
from dataclasses import asdict
from pprint import pformat

from PySide6.QtCore import Signal, QThread, QObject
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QLineEdit,
    QFileDialog,
    QComboBox,
    QListWidget,
    QMessageBox,
    QProgressBar,
)

from typing import Any

from pyama_core.io import load_nd2, ND2Metadata
from pyama_core.processing.workflow import run_complete_workflow
from pyama_qt.widgets import ParameterPanel

logger = logging.getLogger(__name__)


class ND2LoaderThread(QThread):
    """Background thread for loading ND2 files."""

    finished = Signal(object)  # ND2Metadata object
    error = Signal(str)

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            nd2_path = Path(self.filepath)
            _, metadata = load_nd2(nd2_path)
            self.finished.emit(metadata)
        except Exception as e:
            self.error.emit(str(e))


class WorkflowPanel(QWidget):
    """Unified widget for file loading, channel assignment, and processing."""

    # Emitted when user requests processing: {"metadata": ..., "context": ..., "params": ...}
    process_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.metadata = None
        self._selected_pc_index = None
        self._selected_fl_indices = []
        self.setup_ui()

    # --------------------------- UI Construction --------------------------- #
    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)

        # Group 1: Input section
        input_group = QGroupBox("Input")
        input_layout = QVBoxLayout(input_group)

        nd2_header_layout = QHBoxLayout()
        nd2_label = QLabel("ND2 File:")
        self.nd2_button = QPushButton("Browse...")
        self.nd2_button.clicked.connect(self.select_nd2_file)
        nd2_header_layout.addWidget(nd2_label)
        nd2_header_layout.addStretch()
        nd2_header_layout.addWidget(self.nd2_button)

        self.nd2_file = QLineEdit("")
        self.nd2_file.setReadOnly(True)

        input_layout.addLayout(nd2_header_layout)
        input_layout.addWidget(self.nd2_file)

        self.channel_container = QWidget()
        self.channel_container.setEnabled(False)
        channel_layout = QVBoxLayout(self.channel_container)

        pc_layout = QHBoxLayout()
        pc_layout.addWidget(QLabel("Phase Contrast:"), 1)
        self.pc_combo = QComboBox()
        self.pc_combo.addItem("None", None)
        pc_layout.addWidget(self.pc_combo, 1)
        channel_layout.addLayout(pc_layout)

        fl_layout = QHBoxLayout()
        fl_layout.addWidget(QLabel("Fluorescence (multi-select):"), 1)
        self.fl_list = QListWidget()
        try:
            from PySide6.QtWidgets import QAbstractItemView

            self.fl_list.setSelectionMode(QAbstractItemView.MultiSelection)
        except Exception:
            pass
        fl_layout.addWidget(self.fl_list, 1)
        channel_layout.addLayout(fl_layout)

        input_layout.addWidget(self.channel_container)

        layout.addWidget(input_group, 1)

        # Group 2: Output section
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)

        dir_header_layout = QHBoxLayout()
        dir_label = QLabel("Save Directory:")
        self.dir_button = QPushButton("Browse...")
        self.dir_button.clicked.connect(self.select_output_directory)
        dir_header_layout.addWidget(dir_label)
        dir_header_layout.addStretch()
        dir_header_layout.addWidget(self.dir_button)

        self.save_dir = QLineEdit("")
        self.save_dir.setReadOnly(True)

        output_layout.addLayout(dir_header_layout)
        output_layout.addWidget(self.save_dir)

        self.param_panel = ParameterPanel()
        param_definitions = [
            {
                "name": "fov_start",
                "label": "FOV Start",
                "type": "int",
                "default": 0,
                "min": 0,
                "max": 99999,
            },
            {
                "name": "fov_end",
                "label": "FOV End",
                "type": "int",
                "default": 0,
                "min": 0,
                "max": 99999,
            },
            {
                "name": "batch_size",
                "label": "Batch Size",
                "type": "int",
                "default": 2,
                "min": 1,
                "max": 100,
            },
            {
                "name": "n_workers",
                "label": "Workers",
                "type": "int",
                "default": 2,
                "min": 1,
                "max": 32,
            },
        ]
        self.param_panel.set_parameters(param_definitions)
        output_layout.addWidget(self.param_panel)

        # Start button
        self.process_button = QPushButton("Start Complete Workflow")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.start_processing)
        output_layout.addWidget(self.process_button)

        # Progress bar (managed within this panel)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        output_layout.addWidget(self.progress_bar)

        layout.addWidget(output_group, 1)

    # --------------------------- File Loading ------------------------------ #
    def select_nd2_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select ND2 File", "", "ND2 Files (*.nd2);;All Files (*)"
        )
        if filepath:
            self.load_nd2_metadata(filepath)

    def load_nd2_metadata(self, filepath: str):
        self.nd2_file.setText(f"Loading: {Path(filepath).name}")
        self.nd2_button.setEnabled(False)
        logger.info(f"Loading ND2 file: {filepath}")

        self.loader_thread = ND2LoaderThread(filepath)
        self.loader_thread.finished.connect(self.on_nd2_loaded)
        self.loader_thread.error.connect(self.on_load_error)
        self.loader_thread.start()

    def on_nd2_loaded(self, metadata):
        self.metadata = metadata

        try:
            md_dict = asdict(metadata)
        except Exception:
            md_dict = {
                "nd2_path": str(getattr(metadata, "nd2_path", "")),
                "base_name": getattr(metadata, "base_name", ""),
                "height": int(getattr(metadata, "height", 0)),
                "width": int(getattr(metadata, "width", 0)),
                "n_frames": int(getattr(metadata, "n_frames", 0)),
                "n_fovs": int(getattr(metadata, "n_fovs", 0)),
                "n_channels": int(getattr(metadata, "n_channels", 0)),
                "timepoints": list(getattr(metadata, "timepoints", [])),
                "channel_names": list(getattr(metadata, "channel_names", [])),
                "dtype": str(getattr(metadata, "dtype", "")),
            }
        logger.info("ND2 file loaded successfully:\n" + pformat(md_dict))

        self.nd2_file.setText(getattr(metadata, "base_name", ""))
        self.nd2_button.setEnabled(True)

        self.populate_channels(metadata)
        self.channel_container.setEnabled(True)

        # Enable processing now that data is available; final validation happens on start
        self._update_can_process()

    def on_load_error(self, error_msg: str):
        self.nd2_button.setEnabled(True)
        self.nd2_file.setText("No ND2 file selected")
        logger.error(f"Failed to load ND2 file: {error_msg}")
        QMessageBox.critical(
            self, "Loading Error", f"Failed to load ND2 file:\n{error_msg}"
        )

    def populate_channels(self, metadata):
        self.pc_combo.clear()
        self.fl_list.clear()
        self.pc_combo.addItem("None", None)

        for i, channel in enumerate(getattr(metadata, "channel_names", []) or []):
            self.pc_combo.addItem(f"Channel {i}: {channel}", channel)
            self.fl_list.addItem(f"Channel {i}: {channel}")

        self.process_button.setEnabled(True)

    def _update_can_process(self):
        can_process = self.metadata is not None
        self.process_button.setEnabled(can_process)

    # --------------------------- Processing -------------------------------- #
    def select_output_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", ""
        )
        if directory:
            self.save_dir.setText(directory)
            logger.info(f"Output directory selected: {directory}")

    def _gather_channel_selection(self):
        if not self.metadata:
            return None, []

        pc_channel_name = self.pc_combo.currentData()

        selected_fl_items = self.fl_list.selectedItems()
        fl_channel_indices = []
        if selected_fl_items:
            channels = list(getattr(self.metadata, "channel_names", []))
            for item in selected_fl_items:
                text = item.text()
                try:
                    prefix, _ = text.split(": ", 1)
                    idx = int(prefix.replace("Channel ", "").strip())
                except Exception:
                    # Fallback: try lookup by name (rare)
                    name = text
                    idx = channels.index(name) if name in channels else None
                if idx is not None:
                    fl_channel_indices.append(idx)

        pc_channel_idx = None
        if pc_channel_name is not None:
            channel_names = list(getattr(self.metadata, "channel_names", []))
            if pc_channel_name in channel_names:
                pc_channel_idx = channel_names.index(pc_channel_name)

        return pc_channel_idx, fl_channel_indices

    def start_processing(self):
        if not self.metadata:
            return

        pc_idx, fl_indices = self._gather_channel_selection()

        if pc_idx is None and not fl_indices:
            QMessageBox.warning(self, "Warning", "Please select at least one channel")
            return

        values = self.param_panel.get_values() or {}
        p = values.get("params", {}) or {}

        out_dir_str = self.save_dir.text().strip()

        context = {
            "output_dir": Path(out_dir_str) if out_dir_str else None,
            "channels": {
                "pc": int(pc_idx) if pc_idx is not None else 0,
                "fl": list(fl_indices),
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
            QMessageBox.critical(self, "Invalid Settings", str(e))
            return

        # Notify external listeners (optional)
        self.process_requested.emit(
            {"metadata": self.metadata, "context": context, "params": params}
        )

        # Disable UI while processing
        self.param_panel.setEnabled(False)
        self.process_button.setEnabled(False)

        # Start background processing within the panel
        self._start_workflow_processing(
            metadata=self.metadata, context=context, params=params
        )
        logger.info("Starting complete workflow...")

    # --------------------------- External hooks ---------------------------- #
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

    # --------------------------- Internal worker --------------------------- #
    def _start_workflow_processing(
        self, metadata: ND2Metadata, context: dict[str, Any], params: dict
    ):
        self._processing_thread = QThread()

        self._workflow_worker = WorkflowWorker(
            metadata,
            context,
            params.get("fov_start", 0),
            params.get("fov_end"),
            params.get("batch_size", 4),
            params.get("n_workers", 4),
        )
        self._workflow_worker.moveToThread(self._processing_thread)

        self._processing_thread.started.connect(self._workflow_worker.run_processing)
        self._workflow_worker.finished.connect(self._on_processing_finished)
        self._workflow_worker.finished.connect(self._processing_thread.quit)
        self._workflow_worker.finished.connect(self._workflow_worker.deleteLater)
        self._processing_thread.finished.connect(self._processing_thread.deleteLater)

        self._processing_thread.start()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(True)

    def _on_processing_finished(self, success: bool, message: str):
        self.progress_bar.setVisible(False)
        self.processing_finished(success, message)


class WorkflowWorker(QObject):
    """Worker class for running workflow processing in a separate thread."""

    finished = Signal(bool, str)  # success, message

    def __init__(
        self,
        metadata: ND2Metadata,
        context: dict[str, Any],
        fov_start: int,
        fov_end: int | None,
        batch_size: int,
        n_workers: int,
    ):
        super().__init__()
        self.metadata = metadata
        self.context = context
        self.fov_start = fov_start
        self.fov_end = fov_end
        self.batch_size = batch_size
        self.n_workers = n_workers

    def run_processing(self):
        """Run the workflow processing."""
        try:
            success = run_complete_workflow(
                self.metadata,
                self.context,
                fov_start=self.fov_start,
                fov_end=self.fov_end,
                batch_size=self.batch_size,
                n_workers=self.n_workers,
            )

            if success:
                self.finished.emit(
                    True, f"Results saved to {self.context.get('output_dir')}"
                )
            else:
                self.finished.emit(False, "Workflow failed")

        except Exception as e:
            self.finished.emit(False, f"Workflow error: {str(e)}")
