"""Input/configuration panel for the processing workflow."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from pathlib import Path
from typing import Sequence

import pandas as pd
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
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
    QWidget,
)

from pyama_core.io import MicroscopyMetadata
from pyama_core.processing.workflow.services.types import (
    ChannelSelection,
    Channels,
    ProcessingContext,
)

from pyama_qt.constants import DEFAULT_DIR
from pyama_qt.services import WorkerHandle, start_worker
from pyama_qt.components.parameter_panel import ParameterPanel

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN PROCESSING CONFIG PANEL
# =============================================================================


class ProcessingConfigPanel(QWidget):
    """Collects user inputs for running the processing workflow."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    workflow_started = Signal()  # Workflow has started
    workflow_finished = Signal(bool, str)  # Workflow finished (success, message)
    status_message = Signal(str)  # Status message to display
    microscopy_loading_started = Signal()  # When microscopy loading starts
    microscopy_loading_finished = Signal(
        bool, str
    )  # When microscopy loading finishes (success, message)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initialize_state()
        self._build_ui()
        self._connect_signals()

    def _initialize_state(self) -> None:
        """Initialize internal state."""
        self._microscopy_path: Path | None = None
        self._output_dir: Path | None = None
        self._phase_channel: int | None = None
        self._fl_features: dict[int, list[str]] = {}  # channel -> feature list mapping
        self._pc_features: list[str] = []  # phase contrast feature selections
        self._fov_start: int = 0
        self._fov_end: int = 99
        self._batch_size: int = 2
        self._n_workers: int = 2
        self._metadata: MicroscopyMetadata | None = None
        self._microscopy_loader: WorkerHandle | None = None
        self._workflow_runner: WorkerHandle | None = None
        self._available_fl_features: list[str] = []
        self._available_pc_features: list[str] = []

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the main UI layout."""
        layout = QHBoxLayout(self)

        # Create main groups
        self._input_group = self._build_input_group()
        self._output_group = self._build_output_group()

        # Arrange groups
        layout.addWidget(self._input_group, 1)
        layout.addWidget(self._output_group, 1)

        # Initially hide progress bar
        self._progress_bar.setVisible(False)

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers."""
        # File/directory selection
        self._nd2_button.clicked.connect(self._on_microscopy_clicked)
        self._output_button.clicked.connect(self._on_output_clicked)

        # Workflow control
        self._process_button.clicked.connect(self._on_process_clicked)

        # Channel selection
        self._pc_combo.currentIndexChanged.connect(self._emit_channel_selection)
        self._add_button.clicked.connect(self._on_add_channel_feature)
        self._remove_button.clicked.connect(self._on_remove_selected)
        self._mapping_list.itemSelectionChanged.connect(
            self._on_mapping_selection_changed
        )
        self._pc_feature_list.itemSelectionChanged.connect(self._on_pc_features_changed)

        # Parameter changes
        self._param_panel.parameters_changed.connect(self._on_parameters_changed)

    # ------------------------------------------------------------------------
    # LAYOUT BUILDERS
    # ------------------------------------------------------------------------
    def _build_input_group(self) -> QGroupBox:
        """Build the input configuration group."""
        group = QGroupBox("Input")
        layout = QVBoxLayout(group)

        # Microscopy file selection
        header = QHBoxLayout()
        header.addWidget(QLabel("Microscopy File:"))
        header.addStretch()
        self._nd2_button = QPushButton("Browse")
        header.addWidget(self._nd2_button)
        layout.addLayout(header)

        self._microscopy_path_field = QLineEdit()
        self._microscopy_path_field.setReadOnly(True)
        layout.addWidget(self._microscopy_path_field)

        # Channel selection
        self._channel_container = self._build_channel_section()
        layout.addWidget(self._channel_container)

        return group

    def _build_channel_section(self) -> QGroupBox:
        """Build the channel selection section."""
        group = QGroupBox("Channels")
        layout = QVBoxLayout(group)

        # Phase contrast channel
        pc_layout = QVBoxLayout()
        pc_layout.addWidget(QLabel("Phase Contrast"))
        self._pc_combo = QComboBox()
        self._pc_combo.addItem("None", None)
        pc_layout.addWidget(self._pc_combo)
        layout.addLayout(pc_layout)

        pc_feature_layout = QVBoxLayout()
        pc_feature_layout.addWidget(QLabel("Phase Contrast Features"))
        self._pc_feature_list = QListWidget()
        self._pc_feature_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        pc_feature_layout.addWidget(self._pc_feature_list)
        layout.addLayout(pc_feature_layout)

        # Fluorescence channels with feature mapping
        fl_layout = QVBoxLayout()
        fl_layout.addWidget(QLabel("Fluorescence"))

        # Add controls
        add_layout = QHBoxLayout()

        self._fl_channel_combo = QComboBox()
        add_layout.addWidget(self._fl_channel_combo)

        self._feature_combo = QComboBox()
        add_layout.addWidget(self._feature_combo)

        self._add_button = QPushButton("Add")
        add_layout.addWidget(self._add_button)

        fl_layout.addLayout(add_layout)

        # Channel-feature mapping list
        mapping_layout = QVBoxLayout()
        mapping_layout.addWidget(QLabel("Fluorescence Features"))

        self._mapping_list = QListWidget()
        self._mapping_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        mapping_layout.addWidget(self._mapping_list)

        # Remove button
        self._remove_button = QPushButton("Remove Selected")
        self._remove_button.setEnabled(False)
        mapping_layout.addWidget(self._remove_button)

        fl_layout.addLayout(mapping_layout)

        layout.addLayout(fl_layout)

        return group

    def _build_output_group(self) -> QGroupBox:
        """Build the output configuration group."""
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)

        # Output directory selection
        header = QHBoxLayout()
        header.addWidget(QLabel("Save Directory:"))
        header.addStretch()
        self._output_button = QPushButton("Browse")
        header.addWidget(self._output_button)
        layout.addLayout(header)

        self._output_dir_field = QLineEdit()
        self._output_dir_field.setReadOnly(True)
        layout.addWidget(self._output_dir_field)

        # Parameter panel
        self._param_panel = ParameterPanel()
        self._initialize_parameter_defaults()
        layout.addWidget(self._param_panel)

        # Process button
        self._process_button = QPushButton("Start Complete Workflow")
        # Avoid starting with explicit disabled state here; callers/controllers
        # will manage interactivity based on state updates.
        layout.addWidget(self._process_button)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        return group

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot()
    def _on_microscopy_clicked(self) -> None:
        """Handle microscopy file button click."""
        logger.debug("UI Click: Microscopy file browse button")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Microscopy File",
            DEFAULT_DIR,
            "Microscopy Files (*.nd2 *.czi);;ND2 Files (*.nd2);;CZI Files (*.czi);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            logger.info("Microscopy file chosen: %s", file_path)
            self._microscopy_path = Path(file_path)
            self.display_microscopy_path(self._microscopy_path)
            self._load_microscopy(self._microscopy_path)

    @Slot()
    def _on_output_clicked(self) -> None:
        """Handle output directory button click."""
        logger.debug("UI Click: Output directory browse button")
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            logger.info("Output directory chosen: %s", directory)
            self._output_dir = Path(directory)
            self.display_output_directory(self._output_dir)
            self.status_message.emit(f"Output directory set to {directory}")

    @Slot()
    def _on_add_channel_feature(self) -> None:
        """Handle adding channel-feature mapping."""
        channel_data = self._fl_channel_combo.currentData()
        feature = self._feature_combo.currentText()

        if channel_data is None or not feature:
            return

        channel_idx = int(channel_data)

        # Add to mapping
        if channel_idx not in self._fl_features:
            self._fl_features[channel_idx] = []

        if feature not in self._fl_features[channel_idx]:
            self._fl_features[channel_idx].append(feature)
            self._fl_features[channel_idx].sort()  # Keep features ordered

        # Update display
        self._update_mapping_display()

        logger.debug("Added mapping: Channel %d -> %s", channel_idx, feature)

    def _update_mapping_display(self) -> None:
        """Update the mapping list widget display."""
        self._mapping_list.clear()

        for channel_idx in sorted(self._fl_features.keys()):
            features = self._fl_features[channel_idx]
            combo_index = self._fl_channel_combo.findData(channel_idx)
            channel_label = (
                self._fl_channel_combo.itemText(combo_index)
                if combo_index != -1
                else str(channel_idx)
            )
            if not channel_label:
                channel_label = str(channel_idx)
            for feature in features:
                item_text = f"{channel_label} -> {feature}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, (channel_idx, feature))
                self._mapping_list.addItem(item)

        # Enable context menu for removal (optional, kept for advanced users)
        # self._mapping_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # self._mapping_list.customContextMenuRequested.connect(self._show_mapping_context_menu)

    @Slot()
    def _on_mapping_selection_changed(self) -> None:
        """Handle selection change in mapping list."""
        has_selection = bool(self._mapping_list.selectedItems())
        self._remove_button.setEnabled(has_selection)

    @Slot()
    def _on_remove_selected(self) -> None:
        """Remove selected mappings."""
        selected_items = self._mapping_list.selectedItems()
        for item in selected_items:
            self._remove_mapping(item)

    @Slot()
    def _on_pc_features_changed(self) -> None:
        """Handle phase contrast feature selection updates."""
        selected_items = self._pc_feature_list.selectedItems()
        self._pc_features = sorted(item.text() for item in selected_items)
        logger.debug("Phase features updated - %s", self._pc_features)
        self._update_mapping_display()

    def _remove_mapping(self, item: QListWidgetItem) -> None:
        """Remove a channel-feature mapping."""
        channel_idx, feature = item.data(Qt.ItemDataRole.UserRole)

        if (
            channel_idx in self._fl_features
            and feature in self._fl_features[channel_idx]
        ):
            self._fl_features[channel_idx].remove(feature)

            # Remove channel entry if no features left
            if not self._fl_features[channel_idx]:
                del self._fl_features[channel_idx]

            self._update_mapping_display()

            logger.debug("Removed mapping: Channel %d -> %s", channel_idx, feature)

    def _sync_pc_feature_selections(self) -> None:
        """Synchronize phase feature list with stored selections."""
        self._pc_feature_list.blockSignals(True)
        try:
            self._pc_feature_list.clearSelection()
            if self._pc_features:
                selected = set(self._pc_features)
                for idx in range(self._pc_feature_list.count()):
                    item = self._pc_feature_list.item(idx)
                    item.setSelected(item.text() in selected)
        finally:
            self._pc_feature_list.blockSignals(False)
        self._update_mapping_display()

    @Slot()
    def _emit_channel_selection(self) -> None:
        """Store current channel selection."""
        if self._pc_combo.count() == 0:
            return

        # Get phase channel selection
        phase_data = self._pc_combo.currentData()
        self._phase_channel = int(phase_data) if isinstance(phase_data, int) else None
        if self._phase_channel is None and self._pc_features:
            self._pc_features = []
            self._sync_pc_feature_selections()
        else:
            self._update_mapping_display()

        logger.debug(
            "Channels updated - phase=%s, pc_features=%s, fl_features=%s",
            self._phase_channel,
            self._pc_features,
            self._fl_features,
        )

    @Slot()
    def _on_parameters_changed(self) -> None:
        """Handle parameter panel changes."""
        logger.debug("UI Event: Parameters changed")
        df = self._param_panel.get_values_df()
        if df is not None:
            # Convert DataFrame to simple dict and store values
            values = (
                df["value"].to_dict()
                if "value" in df.columns
                else df.iloc[:, 0].to_dict()
            )
            self._fov_start = values.get("fov_start", 0)
            self._fov_end = values.get("fov_end", 99)
            self._batch_size = values.get("batch_size", 2)
            self._n_workers = values.get("n_workers", 2)
            logger.debug("Parameters updated - %s", values)

    @Slot()
    def _on_process_clicked(self) -> None:
        """Handle process button click."""
        logger.debug("UI Click: Process workflow button")
        self._start_workflow()

    # ------------------------------------------------------------------------
    # CONTROLLER-FACING HELPERS
    # ------------------------------------------------------------------------
    def display_microscopy_path(self, path: Path | None) -> None:
        """Show the selected microscopy file."""
        if path:
            self._microscopy_path_field.setText(path.name)
        else:
            self._microscopy_path_field.setText("No microscopy file selected")

    def display_output_directory(self, path: Path | None) -> None:
        """Show the chosen output directory."""
        self._output_dir_field.setText(str(path or ""))

    def load_microscopy_metadata(self, metadata) -> None:
        """Load microscopy metadata and populate channel options."""
        logger.debug("UI Action: Loading microscopy metadata into config panel")

        # Create channel options from metadata
        phase_channels = [("None", None)]
        fluorescence_channels = []

        for i, channel_name in enumerate(metadata.channel_names):
            # Add to both phase and fluorescence initially
            label = f"{i}: {channel_name}" if channel_name else str(i)
            phase_channels.append((label, i))
            fluorescence_channels.append((label, i))

        # Update channel selectors
        self.set_channel_options(phase_channels, fluorescence_channels)

        # Path is already displayed by the click handler

    def set_channel_options(
        self,
        phase_channels: Sequence[tuple[str, int | None]],
        fluorescence_channels: Sequence[tuple[str, int]],
    ) -> None:
        """Populate channel selectors with metadata-driven entries."""
        from pyama_core.processing.extraction.feature import (
            list_fluorescence_features,
            list_phase_features,
        )

        self._available_fl_features = list_fluorescence_features()
        self._available_pc_features = list_phase_features()

        # Update phase channel options
        self._pc_combo.blockSignals(True)
        self._pc_combo.clear()
        for label, value in phase_channels:
            self._pc_combo.addItem(label, value)
        self._pc_combo.blockSignals(False)
        if self._pc_combo.count():
            self._pc_combo.setCurrentIndex(0)

        # Update fluorescence channel dropdown
        self._fl_channel_combo.blockSignals(True)
        self._fl_channel_combo.clear()
        for label, value in fluorescence_channels:
            self._fl_channel_combo.addItem(label, value)
        self._fl_channel_combo.blockSignals(False)
        if self._fl_channel_combo.count():
            self._fl_channel_combo.setCurrentIndex(0)

        # Update feature dropdown
        self._feature_combo.blockSignals(True)
        self._feature_combo.clear()
        for feature in self._available_fl_features:
            self._feature_combo.addItem(feature)
        self._feature_combo.blockSignals(False)
        if self._feature_combo.count():
            self._feature_combo.setCurrentIndex(0)

        # Populate phase contrast feature list
        self._pc_feature_list.blockSignals(True)
        self._pc_feature_list.clear()
        for feature in self._available_pc_features:
            item = QListWidgetItem(feature)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self._pc_feature_list.addItem(item)
        self._pc_feature_list.blockSignals(False)

        self._pc_features = []
        self._sync_pc_feature_selections()

        # Reset fluorescence-feature mappings for the new metadata set
        self._fl_features = {}
        self._update_mapping_display()
        self._mapping_list.clearSelection()
        self._remove_button.setEnabled(False)

    def apply_selected_channels(
        self,
        *,
        phase: int | None,
        fl_features: dict[int, list[str]] | None,
        pc_features: list[str] | None = None,
    ) -> None:
        """Synchronise channel selections without emitting change events."""
        # Update phase channel selection
        self._pc_combo.blockSignals(True)
        try:
            if phase is None:
                self._pc_combo.setCurrentIndex(0)
            else:
                index = self._pc_combo.findData(phase)
                if index != -1:
                    self._pc_combo.setCurrentIndex(index)
        finally:
            self._pc_combo.blockSignals(False)

        # Update fluorescence-feature selections
        normalized: dict[int, list[str]] = {}
        if fl_features:
            for channel, features in fl_features.items():
                if not isinstance(channel, int):
                    continue
                if not features:
                    continue
                normalized[channel] = sorted({str(feature) for feature in features})

        self._fl_features = normalized
        self._update_mapping_display()
        self._mapping_list.clearSelection()
        self._remove_button.setEnabled(False)

        # Update phase contrast feature selections
        self._pc_features = sorted(pc_features or [])
        self._sync_pc_feature_selections()

    def set_processing_active(self, active: bool) -> None:
        """Toggle progress bar visibility based on processing state."""
        if active:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)
            self._progress_bar.setRange(0, 1)

    def set_process_enabled(self, enabled: bool) -> None:
        """Enable or disable the workflow start button."""
        self._process_button.setEnabled(enabled)

    def set_parameter_defaults(self, defaults: pd.DataFrame) -> None:
        """Replace the parameter table with controller-provided defaults."""
        self._param_panel.set_parameters_df(defaults)

    def set_parameter_value(self, name: str, value) -> None:
        """Update a single parameter value."""
        self._param_panel.set_parameter(name, value)

    # ------------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------------
    def _initialize_parameter_defaults(self) -> None:
        """Set up default processing parameters."""
        defaults_data = {
            "fov_start": {"value": 0},
            "fov_end": {"value": 99},
            "batch_size": {"value": 2},
            "n_workers": {"value": 2},
        }
        df = pd.DataFrame.from_dict(defaults_data, orient="index")
        self._param_panel.set_parameters_df(df)

    # ------------------------------------------------------------------------
    # WORKER MANAGEMENT
    # ------------------------------------------------------------------------
    def _load_microscopy(self, path: Path) -> None:
        """Load microscopy metadata in background."""
        logger.info("Loading microscopy metadata from %s", path)
        filename = path.name
        self.status_message.emit(f"Loading {filename}…")
        self.microscopy_loading_started.emit()

        worker = MicroscopyLoaderWorker(path)
        worker.loaded.connect(self._on_microscopy_loaded)
        worker.failed.connect(self._on_microscopy_failed)
        handle = start_worker(
            worker,
            start_method="run",
            finished_callback=self._on_loader_finished,
        )
        self._microscopy_loader = handle

    @Slot(object)
    def _on_microscopy_loaded(self, metadata: MicroscopyMetadata) -> None:
        """Handle microscopy metadata loaded."""
        logger.info("Microscopy metadata loaded")
        self._metadata = metadata
        self.load_microscopy_metadata(metadata)

        # Set fov_start and fov_end based on metadata
        if metadata and metadata.n_fovs > 0:
            self._fov_start = 0
            self._fov_end = metadata.n_fovs - 1
            self.set_parameter_value("fov_start", self._fov_start)
            self.set_parameter_value("fov_end", self._fov_end)

        filename = self._microscopy_path.name if self._microscopy_path else "ND2 file"
        self.status_message.emit(f"{filename} loaded")
        self.microscopy_loading_finished.emit(True, f"{filename} loaded successfully")

    @Slot(str)
    def _on_microscopy_failed(self, message: str) -> None:
        """Handle microscopy loading failure."""
        logger.error("Failed to load ND2: %s", message)
        filename = self._microscopy_path.name if self._microscopy_path else "ND2 file"
        self.status_message.emit(f"Failed to load {filename}: {message}")
        self.microscopy_loading_finished.emit(
            False, f"Failed to load {filename}: {message}"
        )

    @Slot()
    def _on_loader_finished(self) -> None:
        """Handle microscopy loader thread finished."""
        logger.info("ND2 loader thread finished")
        self._microscopy_loader = None

    def _start_workflow(self) -> None:
        """Start the processing workflow."""
        # Validate prerequisites
        if not self._microscopy_path:
            self.status_message.emit("Load an ND2 file before starting the workflow")
            return
        if not self._output_dir:
            self.status_message.emit(
                "Select an output directory before starting the workflow"
            )
            return
        if self._pc_features and self._phase_channel is None:
            self.status_message.emit(
                "Select a phase contrast channel before enabling phase features"
            )
            return
        if (
            self._phase_channel is None
            and not self._fl_features
            and not self._pc_features
        ):
            self.status_message.emit("Select at least one channel to process")
            return

        # Validate parameters
        if not self._validate_parameters():
            return

        # Set up context and run workflow
        pc_selection = (
            ChannelSelection(
                channel=int(self._phase_channel),
                features=list(self._pc_features),
            )
            if self._phase_channel is not None
            else None
        )
        fl_selections = [
            ChannelSelection(channel=int(channel), features=list(features))
            for channel, features in sorted(self._fl_features.items())
        ]

        context = ProcessingContext(
            output_dir=self._output_dir,
            channels=Channels(pc=pc_selection, fl=fl_selections),
            params={},
            time_units="",
        )

        worker = WorkflowRunner(
            metadata=self._metadata,
            context=context,
            fov_start=self._fov_start,
            fov_end=self._fov_end,
            batch_size=self._batch_size,
            n_workers=self._n_workers,
        )
        worker.finished.connect(self._on_workflow_finished)

        handle = start_worker(
            worker,
            start_method="run",
            finished_callback=self._clear_workflow_handle,
        )
        self._workflow_runner = handle
        self.set_processing_active(True)
        self.set_process_enabled(False)
        self.status_message.emit("Running workflow…")
        self.workflow_started.emit()

    def _validate_parameters(self) -> bool:
        """Validate workflow parameters."""
        if not self._metadata:
            return True  # Skip validation if no metadata

        n_fovs = getattr(self._metadata, "n_fovs", 0)

        if self._fov_start < 0:
            self.status_message.emit("FOV start must be >= 0")
            return False
        if self._fov_end < self._fov_start:
            self.status_message.emit("FOV end must be >= start")
            return False
        if self._fov_end >= n_fovs:
            self.status_message.emit(
                f"FOV end ({self._fov_end}) must be less than total FOVs ({n_fovs})"
            )
            return False
        if self._batch_size <= 0:
            self.status_message.emit("Batch size must be positive")
            return False
        if self._n_workers <= 0:
            self.status_message.emit("Number of workers must be positive")
            return False

        return True

    @Slot(bool, str)
    def _on_workflow_finished(self, success: bool, message: str) -> None:
        """Handle workflow completion."""
        logger.info("Workflow finished (success=%s): %s", success, message)
        self.set_processing_active(False)
        self.set_process_enabled(True)
        self.status_message.emit(message)
        self.workflow_finished.emit(success, message)

    def _clear_workflow_handle(self) -> None:
        """Clear workflow handle."""
        logger.info("Workflow thread finished")
        self._workflow_runner = None


# =============================================================================
# BACKGROUND WORKERS
# =============================================================================


class MicroscopyLoaderWorker(QObject):
    """Background worker for loading microscopy metadata."""

    # Signals
    loaded = Signal(object)
    failed = Signal(str)
    finished = Signal()  # Signal to indicate work is complete

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._cancelled = False

    def cancel(self) -> None:
        """Mark this worker as cancelled."""
        self._cancelled = True

    def run(self) -> None:
        """Execute the microscopy loading."""
        try:
            if self._cancelled:
                self.finished.emit()
                return
            from pyama_core.io import load_microscopy_file

            _, metadata = load_microscopy_file(self._path)
            if not self._cancelled:
                self.loaded.emit(metadata)
        except Exception as exc:  # pragma: no cover - propagate to UI
            if not self._cancelled:
                self.failed.emit(str(exc))
        finally:
            # Always emit finished to quit the thread
            self.finished.emit()


class WorkflowRunner(QObject):
    """Background worker for running the processing workflow."""

    # Signals
    finished = Signal(bool, str)

    def __init__(
        self,
        *,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        fov_start: int,
        fov_end: int,
        batch_size: int,
        n_workers: int,
    ) -> None:
        super().__init__()
        self._metadata = metadata
        # Import and use the ensure_context function
        from pyama_core.processing.workflow import ensure_context

        self._context = ensure_context(context)
        self._fov_start = fov_start
        self._fov_end = fov_end
        self._batch_size = batch_size
        self._n_workers = n_workers

    def run(self) -> None:
        """Execute the processing workflow."""
        try:
            from pyama_core.processing.workflow import run_complete_workflow

            success = run_complete_workflow(
                self._metadata,
                self._context,
                fov_start=self._fov_start,
                fov_end=self._fov_end,
                batch_size=self._batch_size,
                n_workers=self._n_workers,
            )
            if success:
                output_dir = self._context.output_dir or "output directory"
                message = f"Results saved to {output_dir}"
                self.finished.emit(True, message)
            else:  # pragma: no cover - defensive branch
                self.finished.emit(False, "Workflow reported failure")
        except Exception as exc:  # pragma: no cover - propagate to UI
            logger.exception("Workflow execution failed")
            self.finished.emit(False, f"Workflow error: {exc}")
