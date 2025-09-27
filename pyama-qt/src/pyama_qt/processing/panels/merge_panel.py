from pathlib import Path
from typing import Any
import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QTableWidget,
    QHeaderView,
    QTableWidgetItem,
    QWidget,
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
from pyama_qt.processing.models import WorkflowStatusModel
from pyama_qt.processing.models import MergeRequest

from pyama_qt.processing.utils import parse_fov_range

logger = logging.getLogger(__name__)


# Keep SampleTable as it's UI-specific
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

            try:
                fovs = parse_fov_range(fovs_text)
            except ValueError as e:
                raise ValueError(f"Row {row + 1} ('{name}'): {e}") from e

            if not fovs:
                raise ValueError(
                    f"Row {row + 1} ('{name}'): At least one FOV is required"
                )

            samples.append({"name": name, "fovs": fovs})

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
        self.sample_edit = QLineEdit()
        sample_row.addWidget(self.sample_edit)
        sample_row.addWidget(sample_browse_btn)
        layout.addLayout(sample_row)

        # Processing Results YAML selector
        processing_results_row = QHBoxLayout()
        processing_results_row.addWidget(QLabel("Processing Results YAML:"))
        processing_results_row.addStretch()
        processing_results_browse_btn = QPushButton("Browse")
        processing_results_browse_btn.clicked.connect(self._choose_processing_results)
        self.processing_results_edit = QLineEdit()
        processing_results_row.addWidget(self.processing_results_edit)
        processing_results_row.addWidget(processing_results_browse_btn)
        layout.addLayout(processing_results_row)

        # CSV folder selector
        data_row = QHBoxLayout()
        data_row.addWidget(QLabel("CSV folder:"))
        data_row.addStretch()
        data_browse_btn = QPushButton("Browse")
        data_browse_btn.clicked.connect(self._choose_data_dir)
        self.data_edit = QLineEdit()
        data_row.addWidget(self.data_edit)
        data_row.addWidget(data_browse_btn)
        layout.addLayout(data_row)

        # Output folder selector
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output folder:"))
        output_row.addStretch()
        output_browse_btn = QPushButton("Browse")
        output_browse_btn.clicked.connect(self._choose_output_dir)
        self.output_edit = QLineEdit()
        output_row.addWidget(self.output_edit)
        output_row.addWidget(output_browse_btn)
        layout.addLayout(output_row)

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

    def set_models(self, status_model: WorkflowStatusModel) -> None:
        self.status_model = status_model
        status_model.statusMessageChanged.connect(self._on_status_changed)
        status_model.errorMessageChanged.connect(self._on_error_changed)
        status_model.mergeStatusChanged.connect(self._on_merge_status_changed)

    def _on_status_changed(self, message: str) -> None:
        # Update UI with status message, e.g., set to a label or status bar
        # For now, placeholder
        pass

    def _on_error_changed(self, message: str) -> None:
        # Handle error display
        self.show_error(message)

    def _on_merge_status_changed(self, status: str) -> None:
        # Update merge status display
        pass

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
            samples = self.table.to_samples()
            self.samples_changed.emit(samples)  # Optional
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save sample.yaml",
                DEFAULT_DIR,
                "YAML Files (*.yaml *.yml);;All Files (*)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if file_path:
                self.save_samples_requested.emit(Path(file_path))
        except ValueError as e:
            self.show_error(str(e))

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
        except ValueError as e:
            self.show_error(str(e))

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

    def show_error(self, message: str) -> None:
        """Display error message to user."""
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(self, "Error", message)

    def show_info(self, message: str) -> None:
        """Display info message to user."""
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "Information", message)
