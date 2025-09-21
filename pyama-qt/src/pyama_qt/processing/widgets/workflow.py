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

from typing import Optional, Tuple, List

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
        """Load ND2 file and emit results."""
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
        self._setup_ui()
        self._connect_signals()
        self._initialize_defaults()

    # --------------------------- UI Construction --------------------------- #
    def _setup_ui(self):
        """Set up the main UI layout."""
        layout = QHBoxLayout(self)

        input_group = self._create_input_group()
        output_group = self._create_output_group()

        layout.addWidget(input_group, 1)
        layout.addWidget(output_group, 1)

    def _create_input_group(self) -> QGroupBox:
        """Create the input section with file loading and channel selection."""
        group = QGroupBox("Input")
        layout = QVBoxLayout(group)

        # ND2 file selection
        nd2_header_layout = QHBoxLayout()
        nd2_label = QLabel("ND2 File:")
        self.nd2_button = QPushButton("Browse")
        nd2_header_layout.addWidget(nd2_label)
        nd2_header_layout.addStretch()
        nd2_header_layout.addWidget(self.nd2_button)

        self.nd2_file = QLineEdit()
        self.nd2_file.setReadOnly(True)

        layout.addLayout(nd2_header_layout)
        layout.addWidget(self.nd2_file)

        # Channel selection (initially disabled)
        self.channel_container = self._create_channel_selection()
        layout.addWidget(self.channel_container)

        return group

    def _create_output_group(self) -> QGroupBox:
        """Create the output section with directory, parameters, and controls."""
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)

        # Output directory selection
        dir_header_layout = QHBoxLayout()
        dir_label = QLabel("Save Directory:")
        self.dir_button = QPushButton("Browse")
        dir_header_layout.addWidget(dir_label)
        dir_header_layout.addStretch()
        dir_header_layout.addWidget(self.dir_button)

        self.save_dir = QLineEdit()
        self.save_dir.setReadOnly(True)

        layout.addLayout(dir_header_layout)
        layout.addWidget(self.save_dir)

        # Parameter panel
        self.param_panel = self._create_parameter_panel()
        layout.addWidget(self.param_panel)

        # Process button
        self.process_button = QPushButton("Start Complete Workflow")
        self.process_button.setEnabled(False)
        layout.addWidget(self.process_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        return group

    def _create_channel_selection(self) -> QWidget:
        """Create the channel selection interface."""
        container = QWidget()
        container.setEnabled(False)
        layout = QVBoxLayout(container)

        # Phase contrast selection
        pc_layout = QVBoxLayout()
        pc_layout.addWidget(QLabel("Phase Contrast:"))
        self.pc_combo = QComboBox()
        self.pc_combo.addItem("None", None)
        pc_layout.addWidget(self.pc_combo)
        layout.addLayout(pc_layout)

        # Fluorescence selection
        fl_layout = QVBoxLayout()
        fl_layout.addWidget(QLabel("Fluorescence (multi-select):"))
        self.fl_list = QListWidget()
        self._setup_fluorescence_list()
        fl_layout.addWidget(self.fl_list)
        layout.addLayout(fl_layout)

        return container

    def _setup_fluorescence_list(self):
        """Configure the fluorescence channel list widget."""
        try:
            from PySide6.QtWidgets import QAbstractItemView

            self.fl_list.setSelectionMode(QAbstractItemView.MultiSelection)
        except ImportError:
            logger.warning(
                "Could not import QAbstractItemView - multi-selection may not work"
            )

    def _create_parameter_panel(self) -> ParameterPanel:
        """Create and initialize the parameter panel."""
        import pandas as pd

        panel = ParameterPanel()

        # Define default parameters
        # -1 for fov_start/fov_end means "process all FOVs"
        params_df = pd.DataFrame(
            {
                "name": ["fov_start", "fov_end", "batch_size", "n_workers"],
                "value": [-1, -1, 2, 2],
            }
        ).set_index("name")

        panel.set_parameters_df(params_df)
        return panel

    def _connect_signals(self):
        """Connect UI signals to their handlers."""
        self.nd2_button.clicked.connect(self.select_nd2_file)
        self.dir_button.clicked.connect(self.select_output_directory)
        self.process_button.clicked.connect(self.start_processing)

    def _initialize_defaults(self):
        """Initialize default values and states."""
        self.nd2_file.setText("")
        self.save_dir.setText("")
        self.progress_bar.setVisible(False)

    # --------------------------- File Loading ------------------------------ #
    def select_nd2_file(self):
        """Open file dialog to select ND2 file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select ND2 File",
            "",
            "ND2 Files (*.nd2);;All Files (*)",
            options=QFileDialog.DontUseNativeDialog,
        )
        if filepath:
            self._load_nd2_metadata(filepath)

    def _load_nd2_metadata(self, filepath: str):
        """Load ND2 metadata in background thread."""
        self.nd2_file.setText(f"Loading: {Path(filepath).name}")
        self.nd2_button.setEnabled(False)
        logger.info(f"Loading ND2 file: {filepath}")

        self._loader_thread = ND2LoaderThread(filepath)
        self._loader_thread.finished.connect(self._on_nd2_loaded)
        self._loader_thread.error.connect(self._on_load_error)
        self._loader_thread.start()

    def _on_nd2_loaded(self, metadata):
        """Handle successful ND2 loading."""
        self.metadata = metadata

        # Log metadata info
        md_dict = self._extract_metadata_dict(metadata)
        logger.info("ND2 file loaded successfully:\n" + pformat(md_dict))

        # Update UI
        self.nd2_file.setText(getattr(metadata, "base_name", "Unknown"))
        self.nd2_button.setEnabled(True)

        # Populate channel selection and enable processing
        self._populate_channels(metadata)
        self.channel_container.setEnabled(True)
        self._update_process_button_state()

    def _extract_metadata_dict(self, metadata) -> dict:
        """Extract metadata as dictionary for logging."""
        try:
            return asdict(metadata)
        except Exception:
            # Fallback for non-dataclass metadata
            return {
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

    def _on_load_error(self, error_msg: str):
        """Handle ND2 loading error."""
        self.nd2_button.setEnabled(True)
        self.nd2_file.setText("No ND2 file selected")
        logger.error(f"Failed to load ND2 file: {error_msg}")
        QMessageBox.critical(
            self, "Loading Error", f"Failed to load ND2 file:\n{error_msg}"
        )

    def _populate_channels(self, metadata):
        """Populate channel selection widgets with available channels."""
        self.pc_combo.clear()
        self.fl_list.clear()

        # Add default "None" option for phase contrast
        self.pc_combo.addItem("None", None)

        # Add channels to both widgets
        channel_names = getattr(metadata, "channel_names", []) or []
        for i, channel in enumerate(channel_names):
            channel_label = f"Channel {i}: {channel}"
            self.pc_combo.addItem(channel_label, channel)
            self.fl_list.addItem(channel_label)

    def _update_process_button_state(self):
        """Update the process button enabled state."""
        can_process = self.metadata is not None
        self.process_button.setEnabled(can_process)

    # --------------------------- Processing -------------------------------- #
    def select_output_directory(self):
        """Open dialog to select output directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", "", options=QFileDialog.DontUseNativeDialog
        )
        if directory:
            self.save_dir.setText(directory)
            logger.info(f"Output directory selected: {directory}")

    def _get_selected_channels(self) -> Tuple[Optional[int], List[int]]:
        """Get the currently selected phase contrast and fluorescence channel indices."""
        if not self.metadata:
            return None, []

        pc_idx = self._get_selected_pc_channel()
        fl_indices = self._get_selected_fl_channels()

        return pc_idx, fl_indices

    def _get_selected_pc_channel(self) -> Optional[int]:
        """Get the selected phase contrast channel index."""
        pc_channel_name = self.pc_combo.currentData()
        if pc_channel_name is None:
            return None

        channel_names = getattr(self.metadata, "channel_names", [])
        try:
            return channel_names.index(pc_channel_name)
        except ValueError:
            logger.warning(f"Phase contrast channel '{pc_channel_name}' not found")
            return None

    def _get_selected_fl_channels(self) -> List[int]:
        """Get the selected fluorescence channel indices."""
        selected_items = self.fl_list.selectedItems()
        if not selected_items:
            return []

        fl_indices = []
        for item in selected_items:
            idx = self._extract_channel_index_from_text(item.text())
            if idx is not None:
                fl_indices.append(idx)

        return fl_indices

    def _extract_channel_index_from_text(self, text: str) -> Optional[int]:
        """Extract channel index from display text like 'Channel 0: DAPI'."""
        try:
            # Expected format: "Channel N: name"
            prefix, _ = text.split(": ", 1)
            return int(prefix.replace("Channel ", "").strip())
        except (ValueError, IndexError):
            logger.warning(f"Could not extract channel index from: {text}")
            return None

    def start_processing(self):
        """Start the workflow processing with validation."""
        if not self.metadata:
            logger.error("No ND2 file loaded")
            return

        try:
            # Get and validate selections
            pc_idx, fl_indices = self._get_selected_channels()
            self._validate_channel_selection(pc_idx, fl_indices)

            # Get and validate parameters
            params = self._get_processing_parameters()
            context = self._create_processing_context(pc_idx, fl_indices)
            self._validate_processing_settings(params, context)

            # Emit signal for external listeners
            self.process_requested.emit(
                {"metadata": self.metadata, "context": context, "params": params}
            )

            # Start processing
            self._start_workflow_processing(self.metadata, context, params)

        except ValueError as e:
            logger.error(f"Validation failed: {e}")
            QMessageBox.critical(self, "Invalid Settings", str(e))

    def _validate_channel_selection(self, pc_idx: Optional[int], fl_indices: List[int]):
        """Validate that at least one channel is selected."""
        if pc_idx is None and not fl_indices:
            raise ValueError("Please select at least one channel")

    def _get_processing_parameters(self) -> dict:
        """Extract and convert processing parameters from the UI."""
        params_df = self.param_panel.get_values_df()
        raw_params = (
            params_df["value"].to_dict()
            if params_df is not None and "value" in params_df.columns
            else {}
        )

        return {
            "fov_start": int(raw_params.get("fov_start", 0)),
            "fov_end": int(raw_params.get("fov_end", 0)),
            "batch_size": int(raw_params.get("batch_size", 2)),
            "n_workers": int(raw_params.get("n_workers", 2)),
        }

    def _create_processing_context(
        self, pc_idx: Optional[int], fl_indices: List[int]
    ) -> dict:
        """Create the processing context dictionary."""
        output_dir_str = self.save_dir.text().strip()
        return {
            "output_dir": Path(output_dir_str) if output_dir_str else None,
            "channels": {
                "pc": int(pc_idx) if pc_idx is not None else 0,
                "fl": list(fl_indices),
            },
            "npy_paths": {},
            "params": {},
        }

    def _validate_processing_settings(self, params: dict, context: dict):
        """Validate processing parameters and context."""
        # Check output directory
        if not context["output_dir"]:
            raise ValueError("Output directory is required")

        # Check FOV range against actual file
        self._validate_fov_range(params)

        # Check positive values
        if params["batch_size"] <= 0:
            raise ValueError("Batch size must be positive")
        if params["n_workers"] <= 0:
            raise ValueError("Number of workers must be positive")

        # Check divisibility (optional but recommended)
        if params["batch_size"] % params["n_workers"] != 0:
            logger.warning("Batch size is not evenly divisible by number of workers")

    def _validate_fov_range(self, params: dict):
        """Validate FOV range against the loaded ND2 metadata."""
        if not self.metadata:
            raise ValueError("No ND2 file loaded")

        n_fovs = getattr(self.metadata, "n_fovs", 0)
        fov_start = params["fov_start"]
        fov_end = params["fov_end"]

        # Handle sentinel values (-1 means "process all")
        if fov_start == -1 and fov_end == -1:
            logger.info(
                f"Using default range: will process all {n_fovs} FOVs (0 to {n_fovs - 1})"
            )
            return  # -1 values are valid and will be handled by run_complete_workflow

        # Handle mixed sentinel values
        if fov_start == -1 or fov_end == -1:
            raise ValueError(
                "Both fov_start and fov_end must be -1 to process all FOVs, or both must be >= 0"
            )

        # Validate explicit ranges
        if fov_start < 0:
            raise ValueError("FOV Start must be >= 0 (or -1 to process all)")

        if fov_end < 0:
            raise ValueError("FOV End must be >= 0 (or -1 to process all)")

        if fov_end < fov_start:
            raise ValueError("FOV End must be >= FOV Start")

        if fov_start >= n_fovs:
            raise ValueError(
                f"FOV Start ({fov_start}) must be < number of FOVs in file ({n_fovs})"
            )

        if fov_end >= n_fovs:
            raise ValueError(
                f"FOV End ({fov_end}) must be < number of FOVs in file ({n_fovs})"
            )

    # --------------------------- External hooks ---------------------------- #
    def update_progress(self, value: int, message: str = ""):
        """Update progress indication (for external use)."""
        if message:
            logger.info(message)

    def processing_finished(self, success: bool, message: str = ""):
        """Handle processing completion with logging and UI updates."""
        if success:
            logger.info("✓ Complete workflow finished successfully")
            if message:
                logger.info(message)
        else:
            logger.error(f"✗ Workflow failed: {message}")

    def processing_error(self, error_message: str):
        """Handle processing error (convenience method)."""
        self.processing_finished(False, error_message)

    # --------------------------- Internal worker --------------------------- #
    def _start_workflow_processing(
        self, metadata: ND2Metadata, context: dict, params: dict
    ):
        """Start workflow processing in background thread."""
        # Disable UI during processing
        self._set_processing_state(True)

        # Create worker thread
        self._processing_thread = QThread()
        self._workflow_worker = WorkflowWorker(
            metadata,
            context,
            params["fov_start"],
            params.get("fov_end"),
            params["batch_size"],
            params["n_workers"],
        )
        self._workflow_worker.moveToThread(self._processing_thread)

        # Connect signals
        self._processing_thread.started.connect(self._workflow_worker.run_processing)
        self._workflow_worker.finished.connect(self._on_processing_finished)
        self._workflow_worker.finished.connect(self._processing_thread.quit)
        self._workflow_worker.finished.connect(self._workflow_worker.deleteLater)
        self._processing_thread.finished.connect(self._processing_thread.deleteLater)

        # Start processing
        self._processing_thread.start()
        logger.info("Starting complete workflow...")

    def _set_processing_state(self, is_processing: bool):
        """Enable/disable UI elements during processing."""
        self.param_panel.setEnabled(not is_processing)
        self.process_button.setEnabled(not is_processing)

        if is_processing:
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)

    def _on_processing_finished(self, success: bool, message: str):
        """Handle processing completion."""
        self._set_processing_state(False)
        self.processing_finished(success, message)


class WorkflowWorker(QObject):
    """Worker class for running workflow processing in a separate thread."""

    finished = Signal(bool, str)  # success, message

    def __init__(
        self,
        metadata: ND2Metadata,
        context: dict,
        fov_start: int,
        fov_end: Optional[int],
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
        """Execute the complete workflow processing."""
        try:
            logger.info(
                f"Starting workflow with FOVs {self.fov_start}-{self.fov_end}, "
                f"batch_size={self.batch_size}, n_workers={self.n_workers}"
            )

            success = run_complete_workflow(
                self.metadata,
                self.context,
                fov_start=self.fov_start,
                fov_end=self.fov_end,
                batch_size=self.batch_size,
                n_workers=self.n_workers,
            )

            self._emit_result(success)

        except Exception as e:
            logger.exception("Workflow processing failed")
            self.finished.emit(False, f"Workflow error: {str(e)}")

    def _emit_result(self, success: bool):
        """Emit the processing result with appropriate message."""
        if success:
            output_dir = self.context.get("output_dir", "unknown location")
            message = f"Results saved to {output_dir}"
            self.finished.emit(True, message)
        else:
            self.finished.emit(False, "Workflow completed but reported failure")
