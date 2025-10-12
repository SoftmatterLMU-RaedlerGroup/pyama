"""FOV assignment and CSV merging utilities without MVC separation."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from pyama_core.io.results_yaml import load_processing_results_yaml, get_channels_from_yaml, get_time_units_from_yaml
from pyama_core.io.processing_csv import get_dataframe
from pyama_qt.config import DEFAULT_DIR
from pyama_qt.views.components.sample_table import SampleTable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MergeRequestPayload:
    """Lightweight container describing merge inputs."""

    sample_yaml: Path
    processing_results_yaml: Path
    data_dir: Path
    output_dir: Path


class ProcessingMergePanel(QGroupBox):
    """Panel responsible for FOV assignment and CSV merging utilities without MVC separation."""

    # Signals for coordination with main processing tab
    load_samples_requested = Signal(Path)
    save_samples_requested = Signal(Path)
    merge_requested = Signal(object)  # Emits MergeRequestPayload
    samples_changed = Signal(list[dict[str, Any]])  # For real-time updates if needed

    def __init__(self, parent=None):
        super().__init__("Merge Configuration", parent)
        self._sample_yaml_path: Path | None = None
        self._processing_results_path: Path | None = None
        self._data_directory: Path | None = None
        self._output_directory: Path | None = None
        
        self.build()

    def build(self) -> None:
        """Build UI."""
        layout = QVBoxLayout(self)

        # Sample configuration
        sample_layout = QHBoxLayout()
        self._sample_label = QLabel("Sample Config:")
        self._sample_edit = QLineEdit()
        self._sample_button = QPushButton("Load...")
        self._sample_save_button = QPushButton("Save...")
        sample_layout.addWidget(self._sample_label)
        sample_layout.addWidget(self._sample_edit)
        sample_layout.addWidget(self._sample_button)
        sample_layout.addWidget(self._sample_save_button)
        layout.addLayout(sample_layout)

        # Processing results
        results_layout = QHBoxLayout()
        self._results_label = QLabel("Processing Results:")
        self._results_edit = QLineEdit()
        self._results_button = QPushButton("Browse...")
        results_layout.addWidget(self._results_label)
        results_layout.addWidget(self._results_edit)
        results_layout.addWidget(self._results_button)
        layout.addLayout(results_layout)

        # Data directory
        data_layout = QHBoxLayout()
        self._data_label = QLabel("Data Directory:")
        self._data_edit = QLineEdit()
        self._data_button = QPushButton("Browse...")
        data_layout.addWidget(self._data_label)
        data_layout.addWidget(self._data_edit)
        data_layout.addWidget(self._data_button)
        layout.addLayout(data_layout)

        # Output directory
        output_layout = QHBoxLayout()
        self._output_label = QLabel("Output Directory:")
        self._output_edit = QLineEdit()
        self._output_button = QPushButton("Browse...")
        output_layout.addWidget(self._output_label)
        output_layout.addWidget(self._output_edit)
        output_layout.addWidget(self._output_button)
        layout.addLayout(output_layout)

        # FOV assignment table
        self.table = SampleTable()
        layout.addWidget(self._create_table_controls())
        layout.addWidget(self.table, 1)

        # Merge button
        self._merge_button = QPushButton("Run Merge")
        layout.addWidget(self._merge_button)

        self.bind()

    def _create_table_controls(self) -> QHBoxLayout:
        """Create controls for the sample table."""
        controls_layout = QHBoxLayout()
        self._add_row_button = QPushButton("Add Row")
        self._remove_row_button = QPushButton("Remove Selected")
        self._add_empty_button = QPushButton("Add Empty")
        controls_layout.addWidget(self._add_row_button)
        controls_layout.addWidget(self._remove_row_button)
        controls_layout.addWidget(self._add_empty_button)
        controls_layout.addStretch()
        return controls_layout

    def bind(self) -> None:
        """Connect signals."""
        self._sample_button.clicked.connect(self._on_sample_load_clicked)
        self._sample_save_button.clicked.connect(self._on_sample_save_clicked)
        self._results_button.clicked.connect(self._on_results_clicked)
        self._data_button.clicked.connect(self._on_data_clicked)
        self._output_button.clicked.connect(self._on_output_clicked)
        self._merge_button.clicked.connect(self._on_merge_clicked)
        self._add_row_button.clicked.connect(self.table.add_empty_row)
        self._remove_row_button.clicked.connect(self.table.remove_selected_row)
        self._add_empty_button.clicked.connect(self.table.add_empty_row)

    def _on_sample_load_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Sample Config", DEFAULT_DIR, "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if path:
            self._sample_edit.setText(path)
            self.load_samples_requested.emit(Path(path))

    def _on_sample_save_clicked(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Sample Config", DEFAULT_DIR, "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if path:
            self.save_samples_requested.emit(Path(path))

    def _on_results_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Processing Results", DEFAULT_DIR, "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if path:
            self._results_edit.setText(path)
            self.set_processing_results_path(Path(path))

    def _on_data_clicked(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Data Directory", DEFAULT_DIR)
        if path:
            self._data_edit.setText(path)
            self.set_data_directory(Path(path))

    def _on_output_clicked(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", DEFAULT_DIR)
        if path:
            self._output_edit.setText(path)
            self.set_output_directory(Path(path))

    def _on_merge_clicked(self) -> None:
        """Emit merge request with current settings."""
        if not all([self._sample_yaml_path, self._processing_results_path, self._data_directory, self._output_directory]):
            logger.warning("Merge requested but not all paths are set")
            return

        payload = MergeRequestPayload(
            sample_yaml=self._sample_yaml_path,
            processing_results_yaml=self._processing_results_path,
            data_dir=self._data_directory,
            output_dir=self._output_directory,
        )
        self.merge_requested.emit(payload)

    def set_sample_yaml_path(self, path: Path) -> None:
        """Update the sample YAML path."""
        self._sample_yaml_path = path
        self._sample_edit.setText(str(path))

    def set_processing_results_path(self, path: Path) -> None:
        """Update the processing results path."""
        self._processing_results_path = path
        self._results_edit.setText(str(path))

    def set_data_directory(self, path: Path) -> None:
        """Update the data directory."""
        self._data_directory = path
        self._data_edit.setText(str(path))

    def set_output_directory(self, path: Path) -> None:
        """Update the output directory."""
        self._output_directory = path
        self._output_edit.setText(str(path))

    def load_samples(self, samples: list[dict[str, Any]]) -> None:
        """Load samples into the table."""
        self.table.clear()
        for sample in samples:
            name = sample.get("name", "")
            fovs = sample.get("fovs", [])
            if isinstance(fovs, list):
                fovs_text = ",".join(map(str, fovs))
            else:
                fovs_text = str(fovs)
            self.table.add_row(name, fovs_text)

    def current_samples(self) -> list[dict[str, Any]]:
        """Get current samples from the table."""
        return self.table.to_samples()