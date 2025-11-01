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
from pyama_pro.constants import DEFAULT_DIR
from pyama_pro.utils import WorkerHandle, start_worker
from pyama_pro.types.processing import MergeRequest

logger = logging.getLogger(__name__)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def read_yaml_config(path: Path) -> dict[str, Any]:
    """Read YAML config file with samples specification.

    Args:
        path: Path to the YAML configuration file

    Returns:
        Dictionary containing the samples configuration

    Raises:
        Exception: If the YAML file cannot be read or parsed
    """
    return read_samples_yaml(path)


# =============================================================================
# MERGE LOGIC
# =============================================================================


def run_merge(
    sample_yaml: Path,
    processing_results: Path,
    output_dir: Path,
) -> str:
    """Execute merge logic - return success message or raise error.

    This function wraps the core merge functionality from pyama_core,
    providing a consistent interface for the Qt GUI components.

    Args:
        sample_yaml: Path to the sample configuration YAML file
        processing_results: Path to the processing results YAML file
        output_dir: Directory where merged results will be saved

    Returns:
        Success message describing the merge operation

    Raises:
        Exception: If the merge operation fails
    """
    return core_run_merge(sample_yaml, processing_results, output_dir)


# =============================================================================
# BACKGROUND WORKER
# =============================================================================


class MergeRunner(QObject):
    """Background worker for running the merge process.

    This class handles the execution of merge operations in a separate
    thread to prevent blocking the UI during long-running merge tasks.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    finished = Signal(bool, str)  # Emitted when merge completes (success, message)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, request: MergeRequest) -> None:
        """Initialize the merge worker.

        Args:
            request: Merge request containing all necessary parameters
        """
        super().__init__()
        self._request = request

    # ------------------------------------------------------------------------
    # WORKER EXECUTION
    # ------------------------------------------------------------------------
    def run(self) -> None:
        """Execute the merge process in the background thread.

        Runs the merge operation and emits the finished signal with
        the result. Any exceptions are caught and reported through
        the finished signal.
        """
        def progress_callback(current: int, total: int, message: str) -> None:
            """Progress callback that logs progress updates."""
            if total > 0:
                progress = int((current / total) * 100)
                logger.info("%s: %d/%d (%d%%)", message, current, total, progress)
            else:
                logger.info("%s: %d", message, current)

        try:
            message = run_merge(
                self._request.sample_yaml,
                self._request.processing_results_yaml,
                self._request.output_dir,
                progress_callback=progress_callback,
            )
            self.finished.emit(True, message)
        except Exception as e:
            logger.exception("Merge failed")
            self.finished.emit(False, str(e))


# =============================================================================
# CUSTOM TABLE WIDGET
# =============================================================================


class SampleTable(QTableWidget):
    """Custom table widget for sample configuration.

    This table widget provides an interface for configuring sample names
    and their associated field-of-view (FOV) ranges. It includes validation
    to ensure data integrity before merge operations.
    """

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the sample table.

        Args:
            parent: Parent widget (default: None)
        """
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
        """Connect signals for the table widget.

        Currently no signals are connected, but this method is kept
        for future extensibility and consistency with other widgets.
        """
        pass

    # ------------------------------------------------------------------------
    # ROW MANAGEMENT
    # ------------------------------------------------------------------------
    def add_empty_row(self) -> None:
        """Add a new empty row to the table.

        Creates a new row with editable items for sample name and FOV range.
        The new row is automatically selected for immediate editing.
        """
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
        """Add a new row with the given data.

        Args:
            name: Sample name
            fovs_text: FOV range specification (e.g., "0-5, 7, 9-11")
        """
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QTableWidgetItem(name))
        self.setItem(row, 1, QTableWidgetItem(fovs_text))

    def remove_selected_row(self) -> None:
        """Remove the currently selected row(s) from the table.

        If multiple rows are selected, all will be removed.
        If no rows are selected, this method does nothing.
        """
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return
        for id in sorted(indexes, key=lambda i: i.row(), reverse=True):
            self.removeRow(id.row())

    def to_samples(self) -> list[dict[str, Any]]:
        """Convert table data to samples list with validation.

        Returns:
            List of sample dictionaries with 'name' and 'fovs' keys

        Raises:
            ValueError: If validation fails (missing names, duplicates, or empty FOVs)
        """
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
        """Load samples data into the table.

        Args:
            samples: List of sample dictionaries with 'name' and 'fovs' keys
        """
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
    """Panel responsible for FOV assignment and CSV merging utilities.

    This panel provides a comprehensive interface for configuring sample
    definitions and executing merge operations on processing results.
    It includes a table for sample configuration and file selection
    controls for specifying input and output paths.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    merge_started = Signal()  # Emitted when merge operation starts
    merge_finished = Signal(bool, str)  # Emitted when merge finishes (success, message)
    samples_loading_started = Signal()  # Emitted when samples loading starts
    samples_loading_finished = Signal(
        bool, str
    )  # Emitted when samples loading finishes (success, message)
    samples_saving_started = Signal()  # Emitted when samples saving starts
    samples_saving_finished = Signal(
        bool, str
    )  # Emitted when samples saving finishes (success, message)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the merge panel.

        Args:
            *args: Positional arguments passed to parent QWidget
            **kwargs: Keyword arguments passed to parent QWidget
        """
        super().__init__(*args, **kwargs)
        self._table: SampleTable | None = None
        self._merge_runner: WorkerHandle | None = None
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build UI components for the merge panel.

        Creates the main layout with two sections:
        1. FOV assignment section with sample table
        2. Merge configuration section with file selectors
        """
        main_layout = QVBoxLayout(self)

        # Create the two main sections
        assign_group = self._create_assign_group()
        merge_group = self._create_merge_group()

        # Add to main layout with equal stretch
        main_layout.addWidget(assign_group, 1)
        main_layout.addWidget(merge_group, 1)

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect all signals for the merge panel.

        Connects button clicks to their respective handlers and
        sets up the merge worker communication.
        """
        # Table buttons
        self._add_btn.clicked.connect(self._on_add_row)
        self._remove_btn.clicked.connect(self._on_remove_row)
        self._load_btn.clicked.connect(self._on_load_requested)
        self._save_btn.clicked.connect(self._on_save_requested)

        # Merge button
        self.run_btn.clicked.connect(self._on_merge_requested)

    # ------------------------------------------------------------------------
    # UI COMPONENT CREATION
    # ------------------------------------------------------------------------
    def _create_assign_group(self) -> QGroupBox:
        """Create the FOV assignment section.

        Returns:
            QGroupBox containing the sample table and control buttons
        """
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
        """Create the merge samples section.

        Returns:
            QGroupBox containing file selectors and merge execution controls
        """
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

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot()
    def _on_add_row(self) -> None:
        """Handle add row button click.

        Adds a new empty row to the sample table for user input.
        """
        self._table.add_empty_row()

    @Slot()
    def _on_remove_row(self) -> None:
        """Handle remove row button click.

        Removes the currently selected row(s) from the sample table.
        """
        self._table.remove_selected_row()

    @Slot()
    def _on_load_requested(self) -> None:
        """Handle load samples button click.

        Opens a file dialog to select a YAML file containing sample
        definitions and loads them into the table.
        """
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
        """Handle save samples button click.

        Opens a file dialog to save the current sample definitions
        to a YAML file.
        """
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
        """Load samples from YAML file.

        Args:
            path: Path to the YAML file containing sample definitions
        """
        self.samples_loading_started.emit()
        try:
            data = read_yaml_config(path)
            samples = data.get("samples", [])
            if not isinstance(samples, list):
                raise ValueError("Invalid YAML: 'samples' must be list")
            self.load_samples(samples)
            self.set_sample_yaml_path(path)
            message = f"Samples loaded from {path}"
            self.samples_loading_finished.emit(True, message)
        except Exception as exc:
            logger.error("Failed to load samples from %s: %s", path, exc)
            message = f"Failed to load samples from {path}: {exc}"
            self.samples_loading_finished.emit(False, message)

    def _save_samples(self, path: Path, samples: list[dict[str, Any]]) -> None:
        """Save samples to YAML file.

        Args:
            path: Path where the YAML file will be saved
            samples: List of sample dictionaries to save
        """
        self.samples_saving_started.emit()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump({"samples": samples}, f, sort_keys=False)
            logger.info("Saved samples to %s", path)
            self.set_sample_yaml_path(path)
            message = f"Samples saved to {path}"
            self.samples_saving_finished.emit(True, message)
        except Exception as exc:
            logger.error("Failed to save samples to %s: %s", path, exc)
            message = f"Failed to save samples to {path}: {exc}"
            self.samples_saving_finished.emit(False, message)

    @Slot()
    def _on_merge_requested(self) -> None:
        """Handle merge button click.

        Validates the input parameters and starts the merge operation
        in a background thread to prevent UI blocking.
        """
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

    @Slot()
    def _on_merge_finished(self, success: bool, message: str) -> None:
        """Handle merge completion.

        Args:
            success: Whether the merge completed successfully
            message: Status message from the merge operation
        """
        if success:
            logger.info("Merge completed: %s", message)
        else:
            logger.error("Merge failed: %s", message)
        self.merge_finished.emit(success, message)

    def _clear_merge_handle(self) -> None:
        """Clear merge handle after completion.

        Called when the background thread finishes to clean up
        the worker handle and allow new merge operations.
        """
        logger.info("Merge thread finished")
        self._merge_runner = None

    @Slot()
    def _choose_sample(self) -> None:
        """Handle sample YAML browse button click.

        Opens a file dialog to select a sample configuration YAML file.
        """
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

    @Slot()
    def _choose_processing_results(self) -> None:
        """Handle processing results YAML browse button click.

        Opens a file dialog to select a processing results YAML file.
        """
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

    @Slot()
    def _choose_output_dir(self) -> None:
        """Handle output directory browse button click.

        Opens a directory dialog to select the output location
        for merged results.
        """
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

    # ------------------------------------------------------------------------
    # CONTROLLER HELPERS
    # ------------------------------------------------------------------------
    def load_samples(self, samples: list[dict[str, Any]]) -> None:
        """Populate the sample table with controller-supplied content.

        Args:
            samples: List of sample dictionaries with 'name' and 'fovs' keys
        """
        if self._table is None:
            self._table = SampleTable(self)
        self._table.load_samples(samples)

    def current_samples(self) -> list[dict[str, Any]]:
        """Return the current sample definitions.

        Returns:
            List of sample dictionaries from the table, or empty list if no table
        """
        if self._table is None:
            return []
        return self._table.to_samples()

    def set_sample_yaml_path(self, path: Path | str) -> None:
        """Set the sample YAML file path in the UI.

        Args:
            path: Path to the sample YAML file
        """
        self.sample_edit.setText(str(path))

    def set_processing_results_path(self, path: Path | str) -> None:
        """Set the processing results YAML file path in the UI.

        Args:
            path: Path to the processing results YAML file
        """
        self.processing_results_edit.setText(str(path))

    def set_output_directory(self, path: Path | str) -> None:
        """Set the output directory path in the UI.

        Args:
            path: Path to the output directory
        """
        self.output_edit.setText(str(path))
