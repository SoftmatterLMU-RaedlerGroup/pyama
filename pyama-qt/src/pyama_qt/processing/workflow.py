"""Processing workflow configuration and execution without MVC separation."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from pyama_core.io import load_microscopy_file, MicroscopyMetadata
from pyama_core.io.results_yaml import load_processing_results_yaml, get_channels_from_yaml, get_time_units_from_yaml
from pyama_core.processing.workflow import ensure_context, run_complete_workflow
from pyama_core.processing.workflow.services.types import Channels, ProcessingContext
from pyama_qt.config import DEFAULT_DIR
from pyama_qt.services import WorkerHandle, start_worker
from pyama_qt.views.components.parameter_panel import ParameterPanel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChannelSelectionPayload:
    """Lightweight payload describing selected channels."""

    phase: int | None
    fluorescence: list[int]


class ProcessingConfigPanel(QGroupBox):
    """Collects user inputs for running the processing workflow without MVC separation."""

    file_selected = Signal(Path)
    output_dir_selected = Signal(Path)
    channels_changed = Signal(object)  # Emits ChannelSelectionPayload as dict-like
    parameters_changed = Signal(dict)  # raw values
    process_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("Workflow Configuration", parent)
        self._is_processing = False
        self._metadata = None
        
        self.build()

    def build(self) -> None:
        layout = QVBoxLayout(self)

        # File input
        file_layout = QHBoxLayout()
        self._file_label = QLabel("Microscopy File:")
        self._file_edit = QLineEdit()
        self._file_button = QPushButton("Browse...")
        file_layout.addWidget(self._file_label)
        file_layout.addWidget(self._file_edit)
        file_layout.addWidget(self._file_button)
        layout.addLayout(file_layout)

        # Output directory
        output_layout = QHBoxLayout()
        self._output_label = QLabel("Output Directory:")
        self._output_edit = QLineEdit()
        self._output_button = QPushButton("Browse...")
        output_layout.addWidget(self._output_label)
        output_layout.addWidget(self._output_edit)
        output_layout.addWidget(self._output_button)
        layout.addLayout(output_layout)

        # Channel selection
        self._phase_combo = QComboBox()
        self._fluorescence_list = QListWidget()
        self._fluorescence_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        channel_layout = QHBoxLayout()
        left_channel_layout = QVBoxLayout()
        right_channel_layout = QVBoxLayout()

        left_channel_layout.addWidget(QLabel("Phase Contrast:"))
        left_channel_layout.addWidget(self._phase_combo)
        right_channel_layout.addWidget(QLabel("Fluorescence:"))
        right_channel_layout.addWidget(self._fluorescence_list)

        channel_layout.addLayout(left_channel_layout, 1)
        channel_layout.addLayout(right_channel_layout, 1)
        layout.addLayout(channel_layout)

        # Parameters
        params_group = QGroupBox("Parameters")
        params_layout = QVBoxLayout(params_group)

        self._fov_start_edit = QLineEdit("0")
        self._fov_end_edit = QLineEdit("99")
        self._batch_size_edit = QLineEdit("2")
        self._n_workers_edit = QLineEdit("2")

        params_form = QVBoxLayout()
        self._add_param_row(params_form, "FOV Start:", self._fov_start_edit)
        self._add_param_row(params_form, "FOV End:", self._fov_end_edit)
        self._add_param_row(params_form, "Batch Size:", self._batch_size_edit)
        self._add_param_row(params_form, "Workers:", self._n_workers_edit)

        params_layout.addLayout(params_form)
        layout.addWidget(params_group)

        # Process button and progress
        self._process_button = QPushButton("Start Processing")
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)

        layout.addWidget(self._process_button)
        layout.addWidget(self._progress_bar)

        self.bind()

    def _add_param_row(self, layout, label_text, widget):
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))
        row.addWidget(widget)
        layout.addLayout(row)

    def bind(self) -> None:
        self._file_button.clicked.connect(self._on_file_clicked)
        self._output_button.clicked.connect(self._on_output_clicked)
        self._phase_combo.currentIndexChanged.connect(self._on_channels_changed)
        self._fluorescence_list.itemSelectionChanged.connect(self._on_channels_changed)
        self._fov_start_edit.textChanged.connect(self._on_params_changed)
        self._fov_end_edit.textChanged.connect(self._on_params_changed)
        self._batch_size_edit.textChanged.connect(self._on_params_changed)
        self._n_workers_edit.textChanged.connect(self._on_params_changed)
        self._process_button.clicked.connect(self._on_process_clicked)

    def _on_file_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Microscopy File", DEFAULT_DIR, "ND2 Files (*.nd2);;All Files (*)"
        )
        if path:
            self._file_edit.setText(path)
            self.file_selected.emit(Path(path))

    def _on_output_clicked(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", DEFAULT_DIR)
        if path:
            self._output_edit.setText(path)
            self.output_dir_selected.emit(Path(path))

    def _on_channels_changed(self) -> None:
        phase_idx = self._phase_combo.currentIndex() - 1  # -1 for "None", 0+ for indices
        phase = phase_idx if phase_idx >= 0 else None
        
        fluorescence = []
        for item in self._fluorescence_list.selectedItems():
            idx = self._fluorescence_list.row(item)
            if idx >= 0:
                fluorescence.append(idx)
        
        payload = ChannelSelectionPayload(phase=phase, fluorescence=fluorescence)
        self.channels_changed.emit(payload)

    def _on_params_changed(self) -> None:
        try:
            fov_start = int(self._fov_start_edit.text())
            fov_end = int(self._fov_end_edit.text())
            batch_size = int(self._batch_size_edit.text())
            n_workers = int(self._n_workers_edit.text())
            
            params = {
                "fov_start": fov_start,
                "fov_end": fov_end,
                "batch_size": batch_size,
                "n_workers": n_workers,
            }
            self.parameters_changed.emit(params)
        except ValueError:
            pass  # Ignore invalid input

    def _on_process_clicked(self) -> None:
        self.process_requested.emit()

    def load_microscopy_metadata(self, metadata: MicroscopyMetadata) -> None:
        """Load metadata and update UI."""
        self._metadata = metadata
        channel_names = getattr(metadata, "channel_names", None)
        n_fovs = getattr(metadata, "n_fovs", None)
        
        # Update UI based on metadata
        self.set_channel_options(metadata)
        if n_fovs:
            self._fov_end_edit.setText(str(n_fovs - 1))

    def set_channel_options(self, metadata) -> None:
        """Set available channel options in the UI."""
        channel_names = getattr(metadata, "channel_names", [])
        
        # Phase contrast options
        self._phase_combo.clear()
        self._phase_combo.addItem("None", None)
        for idx, name in enumerate(channel_names):
            label = f"Channel {idx}: {name}"
            self._phase_combo.addItem(label, idx)

        # Fluorescence options
        self._fluorescence_list.clear()
        for idx, name in enumerate(channel_names):
            item = QListWidgetItem(f"Channel {idx}: {name}")
            item.setSelected(False)
            self._fluorescence_list.addItem(item)

    def set_microscopy_path(self, path: Path) -> None:
        """Update the microscopy file path display."""
        self._file_edit.setText(str(path))

    def set_output_directory(self, path: Path) -> None:
        """Update the output directory display."""
        self._output_edit.setText(str(path))

    def set_processing_active(self, active: bool) -> None:
        """Update processing state indicators."""
        self._is_processing = active
        self._process_button.setEnabled(not active)
        self._progress_bar.setVisible(active)

    def set_process_enabled(self, enabled: bool) -> None:
        """Enable/disable the process button."""
        self._process_button.setEnabled(enabled)