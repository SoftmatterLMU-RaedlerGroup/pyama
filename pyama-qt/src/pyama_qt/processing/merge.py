"""FOV assignment and CSV merging utilities."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import QObject, Signal, Slot, Qt
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

from pyama_core.processing.merge import read_samples_yaml, run_merge as core_run_merge
from pyama_qt.constants import DEFAULT_DIR
from pyama_qt.services import WorkerHandle, start_worker
from pyama_qt.types.processing import MergeRequest

logger = logging.getLogger(__name__)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def read_yaml_config(path: Path) -> dict[str, Any]:
    """Read YAML config file with samples specification."""
    return read_samples_yaml(path)


# =============================================================================
# FEATURE PROCESSING FUNCTIONS
# =============================================================================


# =============================================================================
# MERGE LOGIC
# =============================================================================


def run_merge(
    sample_yaml: Path,
    processing_results: Path,
    output_dir: Path,
) -> str:
    """Execute merge logic - return success message or raise error."""
    return core_run_merge(sample_yaml, processing_results, output_dir)


# =============================================================================
# BACKGROUND WORKER
# =============================================================================


class MergeRunner(QObject):
    """Background worker for running the merge process."""

    # Signals
    finished = Signal(bool, str)

    def __init__(self, request):
        super().__init__()
        self._request = request

    def run(self) -> None:
        """Execute the merge process."""
        try:
            message = run_merge(
                self._request.sample_yaml,
                self._request.processing_results_yaml,
                self._request.output_dir,
            )
            self.finished.emit(True, message)
        except Exception as e:
            logger.exception("Merge failed")
            self.finished.emit(False, str(e))


# =============================================================================
# CUSTOM TABLE WIDGET
# =============================================================================


class SampleTable(QTableWidget):
    """Custom table widget for sample configuration."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # TABLE SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Configure table appearance and behavior."""
        self.setHorizontalHeaderLabels(["Sample Name", "FOVs (e.g., 0-5, 7, 9-11)"])

        # Configure header resizing
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Configure appearance
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

    def _connect_signals(self) -> None:
        """Connect signals for the table widget."""
        pass

    # ------------------------------------------------------------------------
    # ROW MANAGEMENT
    # ------------------------------------------------------------------------
    def add_empty_row(self) -> None:
        """Add a new empty row to the table."""
        row = self.rowCount()
        self.insertRow(row)

        # Create editable items
        name_item = QTableWidgetItem("")
        fovs_item = QTableWidgetItem("")
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        fovs_item.setFlags(fovs_item.flags() | Qt.ItemFlag.ItemIsEditable)

        # Add items to table
        self.setItem(row, 0, name_item)
        self.setItem(row, 1, fovs_item)
        self.setCurrentCell(row, 0)

    def add_row(self, name: str, fovs_text: str) -> None:
        """Add a new row with the given data."""
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QTableWidgetItem(name))
        self.setItem(row, 1, QTableWidgetItem(fovs_text))

    def remove_selected_row(self) -> None:
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return
        for id in sorted(indexes, key=lambda i: i.row(), reverse=True):
            self.removeRow(id.row())

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


class MergePanel(QWidget):
    """Panel responsible for FOV assignment and CSV merging utilities."""

    # Signals
    merge_started = Signal()  # Merge has started
    merge_finished = Signal(bool, str)  # Merge finished (success, message)
    samples_loaded = Signal(str)  # Samples loaded from YAML (path)
    samples_saved = Signal(str)  # Samples saved to YAML (path)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._table: SampleTable | None = None
        self._merge_runner: WorkerHandle | None = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """Build UI components for the merge panel."""
        main_layout = QVBoxLayout(self)

        # Create the two main sections
        assign_group = self._create_assign_group()
        merge_group = self._create_merge_group()

        # Add to main layout with equal stretch
        main_layout.addWidget(assign_group, 1)
        main_layout.addWidget(merge_group, 1)

    def _connect_signals(self) -> None:
        """Connect all signals for the merge panel."""
        # Table buttons
        self._add_btn.clicked.connect(self._on_add_row)
        self._remove_btn.clicked.connect(self._on_remove_row)
        self._load_btn.clicked.connect(self._on_load_requested)
        self._save_btn.clicked.connect(self._on_save_requested)

        # Merge button
        self.run_btn.clicked.connect(self._on_merge_requested)

    def _create_assign_group(self) -> QGroupBox:
        """Create the FOV assignment section."""
        group = QGroupBox("Assign FOVs")
        layout = QVBoxLayout(group)

        # Table
        if self._table is None:
            self._table = SampleTable(self)
        layout.addWidget(self._table)

        # Create buttons
        self._add_btn = QPushButton("Add Sample")
        self._remove_btn = QPushButton("Remove Selected")
        self._load_btn = QPushButton("Load from YAML")
        self._save_btn = QPushButton("Save to YAML")

        # Arrange buttons in rows
        btn_row1 = QHBoxLayout()
        btn_row1.addWidget(self._add_btn)
        btn_row1.addWidget(self._remove_btn)

        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(self._load_btn)
        btn_row2.addWidget(self._save_btn)

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

        # CSV folder selector - use processing results YAML directory
        # (This section is now removed as the input directory is automatically
        # derived from the processing results YAML file path)

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
        self.run_btn = QPushButton("Run Merge")
        layout.addWidget(self.run_btn)

        return group

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    @Slot()
    def _on_add_row(self) -> None:
        """Add a new row to the table."""
        self._table.add_empty_row()

    @Slot()
    def _on_remove_row(self) -> None:
        """Remove selected row from the table."""
        self._table.remove_selected_row()

    @Slot()
    def _on_load_requested(self) -> None:
        """Load samples from YAML file."""
        logger.debug("UI Click: Load samples button")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._load_samples(Path(file_path))

    @Slot()
    def _on_save_requested(self) -> None:
        """Save samples to YAML file."""
        logger.debug("UI Click: Save samples button")
        try:
            samples = self.current_samples()
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save sample.yaml",
                DEFAULT_DIR,
                "YAML Files (*.yaml *.yml);;All Files (*)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if file_path:
                self._save_samples(Path(file_path), samples)
        except ValueError as exc:
            logger.error("Failed to save samples: %s", exc)

    def _load_samples(self, path: Path) -> None:
        """Load samples from YAML file."""
        try:
            data = read_yaml_config(path)
            samples = data.get("samples", [])
            if not isinstance(samples, list):
                raise ValueError("Invalid YAML: 'samples' must be list")
            self.load_samples(samples)
            self.set_sample_yaml_path(path)
            self.samples_loaded.emit(str(path))
        except Exception as exc:
            logger.error("Failed to load samples from %s: %s", path, exc)

    def _save_samples(self, path: Path, samples: list[dict[str, Any]]) -> None:
        """Save samples to YAML file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump({"samples": samples}, f, sort_keys=False)
            logger.info("Saved samples to %s", path)
            self.set_sample_yaml_path(path)
            self.samples_saved.emit(str(path))
        except Exception as exc:
            logger.error("Failed to save samples to %s: %s", path, exc)

    def _on_merge_requested(self) -> None:
        """Run merge after validation."""
        logger.debug("UI Click: Run merge button")

        if self._merge_runner:
            logger.warning("Merge already running")
            return

        try:
            sample_text = self.sample_edit.text().strip()
            processing_text = self.processing_results_edit.text().strip()
            output_text = self.output_edit.text().strip()

            if not all([sample_text, processing_text, output_text]):
                return

            # Use the processing results YAML directory as input directory
            sample_yaml_path = Path(sample_text).expanduser()
            processing_results_yaml_path = Path(processing_text).expanduser()
            output_dir = Path(output_text).expanduser()

            request = MergeRequest(
                sample_yaml=sample_yaml_path,
                processing_results_yaml=processing_results_yaml_path,
                output_dir=output_dir,
            )

            # Run merge in background
            worker = MergeRunner(request)
            worker.finished.connect(self._on_merge_finished)
            handle = start_worker(
                worker,
                start_method="run",
                finished_callback=self._clear_merge_handle,
            )
            self._merge_runner = handle
            self.merge_started.emit()

        except Exception as exc:
            logger.error("Failed to start merge: %s", exc)

    def _on_merge_finished(self, success: bool, message: str) -> None:
        """Handle merge completion."""
        if success:
            logger.info("Merge completed: %s", message)
            # Extract output directory from the message for a cleaner status

        else:
            logger.error("Merge failed: %s", message)
        self.merge_finished.emit(success, message)

    def _clear_merge_handle(self) -> None:
        """Clear merge handle."""
        logger.info("Merge thread finished")
        self._merge_runner = None

    def _choose_sample(self) -> None:
        """Browse for sample YAML file."""
        logger.debug("UI Click: Browse sample YAML button")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sample.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            logger.debug("UI Action: Set sample YAML path - %s", path)
            self.sample_edit.setText(path)

    def _choose_processing_results(self) -> None:
        """Browse for processing results YAML file."""
        logger.debug("UI Click: Browse processing results YAML button")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select processing_results.yaml",
            DEFAULT_DIR,
            "YAML Files (*.yaml *.yml)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            logger.debug("UI Action: Set processing results YAML path - %s", path)
            self.processing_results_edit.setText(path)

        # Connect signals for the table widget
        pass

    def _choose_output_dir(self) -> None:
        """Browse for output directory."""
        logger.debug("UI Click: Browse output directory button")
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output folder",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            logger.debug("UI Action: Set output directory - %s", path)
            self.output_edit.setText(path)

    # ------------------------------------------------------------------
    # Controller helpers
    # ------------------------------------------------------------------
    def load_samples(self, samples: list[dict[str, Any]]) -> None:
        """Populate the sample table with controller-supplied content."""
        if self._table is None:
            self._table = SampleTable(self)
        self._table.load_samples(samples)

    def current_samples(self) -> list[dict[str, Any]]:
        """Return the current sample definitions."""
        if self._table is None:
            return []
        return self._table.to_samples()

    def set_sample_yaml_path(self, path: Path | str) -> None:
        self.sample_edit.setText(str(path))

    def set_processing_results_path(self, path: Path | str) -> None:
        self.processing_results_edit.setText(str(path))

    def set_output_directory(self, path: Path | str) -> None:
        self.output_edit.setText(str(path))
