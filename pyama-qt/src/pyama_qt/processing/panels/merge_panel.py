from __future__ import annotations

import logging

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal

from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QLineEdit,
    QFileDialog,
    QPushButton,
    QHBoxLayout,
    QLabel,
)

from pyama_qt.config import DEFAULT_DIR
from pyama_qt.ui import ModelBoundPanel
from pyama_qt.processing.requests import MergeRequest
from pyama_qt.components.sample_table import SampleTable

logger = logging.getLogger(__name__)


class ProcessingMergePanel(ModelBoundPanel):
    """Panel responsible for FOV assignment and CSV merging utilities."""

    # Signals for controller
    load_samples_requested = Signal(Path)
    save_samples_requested = Signal(Path)
    merge_requested = Signal(MergeRequest)
    samples_changed = Signal(list[dict[str, Any]])  # For real-time updates if needed

    def __init__(self, *args, **kwargs):
        self.table: SampleTable | None = None
        super().__init__(*args, **kwargs)

    def build(self) -> None:
        """Build UI using BasePanel hook."""
        main_layout = QVBoxLayout(self)

        # Create the two main sections
        assign_group = self._create_assign_group()
        merge_group = self._create_merge_group()

        # Add to main layout with equal stretch
        main_layout.addWidget(assign_group, 1)
        main_layout.addWidget(merge_group, 1)

    def _create_assign_group(self) -> QGroupBox:
        """Create the FOV assignment section."""
        group = QGroupBox("Assign FOVs")
        layout = QVBoxLayout(group)

        # Table
        if self.table is None:
            self.table = SampleTable(self)
        layout.addWidget(self.table)

        # Create buttons
        self.add_btn = QPushButton("Add Sample")
        self.remove_btn = QPushButton("Remove Selected")
        self.load_btn = QPushButton("Load from YAML")
        self.save_btn = QPushButton("Save to YAML")

        # Arrange buttons in rows
        btn_row1 = QHBoxLayout()
        btn_row1.addWidget(self.add_btn)
        btn_row1.addWidget(self.remove_btn)

        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(self.load_btn)
        btn_row2.addWidget(self.save_btn)

        layout.addLayout(btn_row1)
        layout.addLayout(btn_row2)

        return group

    def _create_merge_group(self) -> QGroupBox:
        """Create the merge samples section."""
        group = QGroupBox("Merge Samples")
        layout = QVBoxLayout(group)

        # File/folder selectors
        # Sample YAML selector
        sample_row = QHBoxLayout()
        sample_row.addWidget(QLabel("Sample YAML:"))
        sample_row.addStretch()
        sample_browse_btn = QPushButton("Browse")
        sample_browse_btn.clicked.connect(self._choose_sample)
        sample_row.addWidget(sample_browse_btn)
        layout.addLayout(sample_row)
        self.sample_edit = QLineEdit()
        layout.addWidget(self.sample_edit)

        # Processing Results YAML selector
        processing_results_row = QHBoxLayout()
        processing_results_row.addWidget(QLabel("Processing Results YAML:"))
        processing_results_row.addStretch()
        processing_results_browse_btn = QPushButton("Browse")
        processing_results_browse_btn.clicked.connect(self._choose_processing_results)
        processing_results_row.addWidget(processing_results_browse_btn)
        layout.addLayout(processing_results_row)
        self.processing_results_edit = QLineEdit()
        layout.addWidget(self.processing_results_edit)

        # CSV folder selector
        data_row = QHBoxLayout()
        data_row.addWidget(QLabel("CSV folder:"))
        data_row.addStretch()
        data_browse_btn = QPushButton("Browse")
        data_browse_btn.clicked.connect(self._choose_data_dir)
        data_row.addWidget(data_browse_btn)
        layout.addLayout(data_row)
        self.data_edit = QLineEdit()
        layout.addWidget(self.data_edit)

        # Output folder selector
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output folder:"))
        output_row.addStretch()
        output_browse_btn = QPushButton("Browse")
        output_browse_btn.clicked.connect(self._choose_output_dir)
        output_row.addWidget(output_browse_btn)
        layout.addLayout(output_row)
        self.output_edit = QLineEdit()
        layout.addWidget(self.output_edit)

        # Run button
        actions = QHBoxLayout()
        self.run_btn = QPushButton("Run Merge")
        actions.addWidget(self.run_btn)
        layout.addLayout(actions)

        return group

    def bind(self) -> None:
        """Connect signals in ModelBoundPanel hook."""
        # Table buttons
        self.add_btn.clicked.connect(self.table.add_empty_row)
        self.remove_btn.clicked.connect(self.table.remove_selected_row)
        self.load_btn.clicked.connect(self._on_load_requested)
        self.save_btn.clicked.connect(self._on_save_requested)

        # Merge button
        self.run_btn.clicked.connect(self._on_merge_requested)

        # Optional: Connect table changes to emit samples_changed if real-time needed
        # For now, emit on load/save

    def _on_load_requested(self) -> None:
        """Request load via signal."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self.load_samples_requested.emit(Path(file_path))

    def _on_save_requested(self) -> None:
        """Request save via signal."""
        try:
            # Note: samples_changed signal not currently connected, so skip emit
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save sample.yaml",
                DEFAULT_DIR,
                "YAML Files (*.yaml *.yml);;All Files (*)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if file_path:
                self.save_samples_requested.emit(Path(file_path))
        except ValueError:
            pass

    def _on_merge_requested(self) -> None:
        """Request merge via signal after basic validation."""
        try:
            sample_path = Path(self.sample_edit.text()).expanduser()
            processing_results_path = Path(
                self.processing_results_edit.text()
            ).expanduser()
            data_dir = Path(self.data_edit.text()).expanduser()
            output_dir = Path(self.output_edit.text()).expanduser()

            # Basic path validation in view
            if not all([sample_path, processing_results_path, data_dir, output_dir]):
                raise ValueError("All paths must be specified")

            self.merge_requested.emit(
                MergeRequest(sample_path, processing_results_path, data_dir, output_dir)
            )
        except ValueError:
            pass

    def _choose_sample(self) -> None:
        """Browse for sample YAML file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.sample_edit.setText(path)

    def _choose_processing_results(self) -> None:
        """Browse for processing results YAML file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select processing_results.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.processing_results_edit.setText(path)

    def _choose_data_dir(self) -> None:
        """Browse for CSV data directory."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select FOV CSV folder",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.data_edit.setText(path)

    def _choose_output_dir(self) -> None:
        """Browse for output directory."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output folder",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.output_edit.setText(path)
