"""FOV assignment and CSV merging utilities without MVC separation."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QTableWidget,
    QHeaderView,
    QTableWidgetItem,
    QWidget,
)

from pyama_core.io.results_yaml import load_processing_results_yaml, get_channels_from_yaml, get_time_units_from_yaml
from pyama_core.io.processing_csv import get_dataframe
from pyama_qt.config import DEFAULT_DIR

logger = logging.getLogger(__name__)


class SampleTable(QTableWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["Sample Name", "FOVs (e.g., 0-5, 7, 9-11)"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

    def add_empty_row(self) -> None:
        row = self.rowCount()
        self.insertRow(row)
        name_item = QTableWidgetItem("")
        fovs_item = QTableWidgetItem("")
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        fovs_item.setFlags(fovs_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, 0, name_item)
        self.setItem(row, 1, fovs_item)
        self.setCurrentCell(row, 0)

    def add_row(self, name: str, fovs_text: str) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QTableWidgetItem(name))
        self.setItem(row, 1, QTableWidgetItem(fovs_text))

    def remove_selected_row(self) -> None:
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return
        for idx in sorted(indexes, key=lambda i: i.row(), reverse=True):
            self.removeRow(idx.row())

    def to_samples(self) -> list[dict[str, Any]]:
        """Convert table data to samples list with validation. Emit error if invalid."""
        samples = []
        seen_names = set()

        for row in range(self.rowCount()):
            name_item = self.item(row, 0)
            fovs_item = self.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            fovs_text = (fovs_item.text() if fovs_item else "").strip()

            # Validate name
            if not name:
                raise ValueError(f"Row {row + 1}: Sample name is required")
            if name in seen_names:
                raise ValueError(f"Row {row + 1}: Duplicate sample name '{name}'")
            seen_names.add(name)

            # Parse and validate FOVs
            if not fovs_text:
                raise ValueError(
                    f"Row {row + 1} ('{name}'): At least one FOV is required"
                )

            samples.append({"name": name, "fovs": fovs_text})

        return samples

    def load_samples(self, samples: list[dict[str, Any]]) -> None:
        """Load samples data into the table."""
        self.setRowCount(0)
        for sample in samples:
            name = str(sample.get("name", ""))
            fovs_val = sample.get("fovs", [])

            if isinstance(fovs_val, list):
                fovs_text = ", ".join(str(int(v)) for v in fovs_val)
            elif isinstance(fovs_val, str):
                fovs_text = fovs_val
            else:
                fovs_text = ""

            self.add_row(name, fovs_text)



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
        layout.addLayout(self._create_table_controls())
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