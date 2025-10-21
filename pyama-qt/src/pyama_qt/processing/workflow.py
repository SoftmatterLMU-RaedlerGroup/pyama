"""Input/configuration panel for the processing workflow."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
import threading
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

from pyama_core.io import MicroscopyMetadata, load_microscopy_file
from pyama_core.processing.extraction.features import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama_core.processing.workflow import ensure_context, run_complete_workflow
from pyama_core.processing.workflow.services.types import (
    ChannelSelection,
    Channels,
    ProcessingContext,
)
from pyama_qt.components.parameter_table import ParameterTable
from pyama_qt.constants import DEFAULT_DIR
from pyama_qt.utils import WorkerHandle, start_worker

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN PROCESSING CONFIG PANEL
# =============================================================================


class WorkflowPanel(QWidget):
    """Collects user inputs for running the processing workflow.

    This panel provides a comprehensive interface for configuring
    and executing the image processing workflow. It includes controls
    for file selection, channel configuration, feature selection,
    and processing parameters.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    workflow_started = Signal()  # Emitted when workflow execution starts
    workflow_finished = Signal(
        bool, str
    )  # Emitted when workflow finishes (success, message)
    microscopy_loading_started = Signal()  # Emitted when microscopy file loading starts
    microscopy_loading_finished = Signal(
        bool, str
    )  # Emitted when microscopy loading finishes (success, message)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the workflow panel.

        Args:
            *args: Positional arguments passed to parent QWidget
            **kwargs: Keyword arguments passed to parent QWidget
        """
        super().__init__(*args, **kwargs)
        self._initialize_state()
        self._build_ui()
        self._connect_signals()

    def _initialize_state(self) -> None:
        """Initialize internal state variables.

        Sets up all the default values and state tracking variables
        used throughout the workflow panel.
        """
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
        self._cancel_button: QPushButton

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the main UI layout.

        Creates a horizontal layout with input configuration on the left
        and output configuration on the right. The progress bar is
        initially hidden and shown only during processing.
        """
        layout = QHBoxLayout(self)

        # Create main groups
        self._input_group = self._build_input_group()
        self._output_group = self._build_output_group()

        # Arrange groups with equal spacing
        layout.addWidget(self._input_group, 1)
        layout.addWidget(self._output_group, 1)

        # Initially hide progress bar
        self._progress_bar.setVisible(False)

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to their respective handlers.

        Sets up all the signal/slot connections for user interactions,
        including file selection, channel configuration, and workflow control.
        """
        # File/directory selection
        self._nd2_button.clicked.connect(self._on_microscopy_clicked)
        self._output_button.clicked.connect(self._on_output_clicked)

        # Workflow control
        self._process_button.clicked.connect(self._on_process_clicked)

        # Channel selection
        self._pc_combo.currentIndexChanged.connect(self._on_pc_channel_selection)
        self._add_button.clicked.connect(self._on_add_channel_feature)
        self._remove_button.clicked.connect(self._on_remove_selected)
        self._mapping_list.itemSelectionChanged.connect(
            self._on_mapping_selection_changed
        )
        self._pc_feature_list.itemSelectionChanged.connect(self._on_pc_features_changed)

        # Parameter changes
        self._param_panel.parameters_changed.connect(self._on_parameters_changed)

        # Process and cancel buttons
        self._cancel_button.clicked.connect(self._on_cancel_workflow)

    # ------------------------------------------------------------------------
    # LAYOUT BUILDERS
    # ------------------------------------------------------------------------
    def _build_input_group(self) -> QGroupBox:
        """Build the input configuration group.

        Creates the input section containing microscopy file selection
        and channel configuration controls.

        Returns:
            QGroupBox containing all input configuration widgets
        """
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
        """Build the channel selection section.

        Creates controls for selecting phase contrast and fluorescence
        channels, along with their associated features.

        Returns:
            QGroupBox containing channel selection widgets
        """
        group = QGroupBox("Channels")
        layout = QVBoxLayout(group)

        # Phase contrast channel
        pc_layout = QVBoxLayout()
        pc_layout.addWidget(QLabel("Phase Contrast"))
        self._pc_combo = QComboBox()
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
        """Build the output configuration group.

        Creates the output section containing directory selection,
        parameter configuration, and workflow control buttons.

        Returns:
            QGroupBox containing all output configuration widgets
        """
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
        self._param_panel = ParameterTable()
        self._initialize_parameter_defaults()
        layout.addWidget(self._param_panel)

        # Process button
        self._process_button = QPushButton("Start Complete Workflow")
        # Avoid starting with explicit disabled state here; callers/controllers
        # will manage interactivity based on state updates.
        layout.addWidget(self._process_button)

        # Cancel button
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setEnabled(False)  # Start disabled
        layout.addWidget(self._cancel_button)

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
        """Handle microscopy file button click.

        Opens a file dialog to select a microscopy file (ND2 or CZI format)
        and initiates loading of its metadata for channel configuration.
        """
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
        """Handle output directory button click.

        Opens a directory dialog to select the output location
        for processing results.
        """
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

    @Slot()
    def _on_add_channel_feature(self) -> None:
        """Handle adding channel-feature mapping.

        Adds the selected fluorescence channel and feature combination
        to the mapping list. Duplicates are prevented and features
        are kept in alphabetical order.
        """
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
        """Update the mapping list widget display.

        Refreshes the fluorescence channel-feature mapping list to show
        the current state of the internal mapping dictionary.
        """
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
        """Handle selection change in mapping list.

        Enables or disables the remove button based on whether
        any mappings are currently selected.
        """
        has_selection = bool(self._mapping_list.selectedItems())
        self._remove_button.setEnabled(has_selection)

    @Slot()
    def _on_remove_selected(self) -> None:
        """Remove selected mappings.

        Removes all currently selected channel-feature mappings
        from the internal state and updates the display.
        """
        selected_items = self._mapping_list.selectedItems()
        for item in selected_items:
            self._remove_mapping(item)

    @Slot()
    def _on_pc_features_changed(self) -> None:
        """Handle phase contrast feature selection updates.

        Updates the internal phase contrast feature list when the
        user changes the selection in the phase contrast feature list.
        """
        selected_items = self._pc_feature_list.selectedItems()
        self._pc_features = sorted(item.text() for item in selected_items)
        logger.debug("Phase features updated - %s", self._pc_features)

    def _remove_mapping(self, item: QListWidgetItem) -> None:
        """Remove a channel-feature mapping.

        Args:
            item: The list item representing the mapping to remove
        """
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
        """Synchronize phase feature list with stored selections.

        Updates the UI to reflect the current internal state of
        phase contrast feature selections without emitting signals.
        """
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

    @Slot()
    def _on_pc_channel_selection(self) -> None:
        """Handle phase contrast channel selection change.

        Updates the internal phase channel selection when the user
        changes the selected phase contrast channel.
        """
        if self._pc_combo.count() == 0:
            return

        # Get phase channel selection
        phase_data = self._pc_combo.currentData()
        self._phase_channel = int(phase_data) if isinstance(phase_data, int) else None

        logger.debug(
            "Channels updated - phase=%s, pc_features=%s, fl_features=%s",
            self._phase_channel,
            self._pc_features,
            self._fl_features,
        )

    @Slot()
    def _on_parameters_changed(self) -> None:
        """Handle parameter panel changes (UI→model only).

        Updates the internal parameter values when the user modifies
        them in the parameter table. This follows the one-way binding
        pattern where UI changes update the model but not vice versa.
        """
        # Only read values when user has manual mode enabled
        if not self._param_panel.is_manual_mode():
            return

        df = self._param_panel.get_values_df()
        if df is not None:
            # Convert DataFrame to simple dict - update all parameters from UI
            values = (
                df["value"].to_dict()
                if "value" in df.columns
                else df.iloc[:, 0].to_dict()
            )

            # Update internal model from UI (one-way: UI→model)
            self._fov_start = values.get("fov_start", 0)
            self._fov_end = values.get("fov_end", 99)
            self._batch_size = values.get("batch_size", 2)
            self._n_workers = values.get("n_workers", 2)

            logger.debug(
                "Workflow parameters updated from UI - fov_start=%d, fov_end=%d, batch_size=%d, n_workers=%d",
                self._fov_start,
                self._fov_end,
                self._batch_size,
                self._n_workers,
            )

    @Slot()
    def _on_process_clicked(self) -> None:
        """Handle process button click.

        Initiates the workflow execution after validating all
        required inputs and parameters.
        """
        logger.debug("UI Click: Process workflow button")
        self._start_workflow()

    @Slot()
    def _on_cancel_workflow(self) -> None:
        """Handle cancel button click.

        Cancels the currently running workflow if one exists
        and re-enables the process button.
        """
        logger.debug("UI Click: Cancel workflow button")
        if self._workflow_runner:
            logger.info("Cancelling workflow execution")
            self._workflow_runner.cancel()
            # Don't immediately re-enable process button - wait for workflow to finish
            # The workflow_finished signal will handle the UI state update
        else:
            # No workflow running, just update UI state
            self.set_process_enabled(True)

    # ------------------------------------------------------------------------
    # CONTROLLER-FACING HELPERS
    # ------------------------------------------------------------------------
    def display_microscopy_path(self, path: Path | None) -> None:
        """Show the selected microscopy file in the UI.

        Args:
            path: Path to the selected microscopy file, or None
        """
        if path:
            self._microscopy_path_field.setText(path.name)
        else:
            self._microscopy_path_field.setText("No microscopy file selected")

    def display_output_directory(self, path: Path | None) -> None:
        """Show the chosen output directory in the UI.

        Args:
            path: Path to the selected output directory, or None
        """
        self._output_dir_field.setText(str(path or ""))

    def load_microscopy_metadata(self, metadata: MicroscopyMetadata) -> None:
        """Load microscopy metadata and populate channel options.

        Args:
            metadata: MicroscopyMetadata object containing channel information
        """
        logger.debug("UI Action: Loading microscopy metadata into config panel")

        # Create channel options from metadata
        phase_channels = []
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
        """Populate channel selectors with metadata-driven entries.

        Args:
            phase_channels: Sequence of (label, value) tuples for phase channels
            fluorescence_channels: Sequence of (label, value) tuples for fluorescence channels
        """
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
            self._on_pc_channel_selection()

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
        """Synchronize channel selections without emitting change events.

        Args:
            phase: Phase channel index or None
            fl_features: Dictionary mapping fluorescence channels to feature lists
            pc_features: List of phase contrast features
        """
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
        """Toggle progress bar visibility based on processing state.

        Args:
            active: Whether processing is currently active
        """
        if active:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)
            self._progress_bar.setRange(0, 1)

    def set_process_enabled(self, enabled: bool) -> None:
        """Enable or disable the workflow start button.

        Args:
            enabled: Whether the process button should be enabled
        """
        self._process_button.setEnabled(enabled)
        self._cancel_button.setEnabled(
            not enabled
        )  # Cancel enabled when processing is disabled

    def set_parameter_defaults(self, defaults: pd.DataFrame) -> None:
        """Replace the parameter table with controller-provided defaults.

        Args:
            defaults: DataFrame containing default parameter values
        """
        self._param_panel.set_parameters_df(defaults)

    # ------------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------------
    def _initialize_parameter_defaults(self) -> None:
        """Set up default processing parameters.

        Initializes the parameter table with sensible default values
        for FOV range, batch size, and worker count.
        """
        defaults_data = {
            "fov_start": {"value": 0},
            "fov_end": {"value": 99},
            "batch_size": {"value": 2},
            "n_workers": {"value": 2},
        }
        df = pd.DataFrame.from_dict(defaults_data, orient="index")
        self._param_panel.set_parameters_df(df)

    def _update_fov_parameters(self, fov_start: int, fov_end: int) -> None:
        """Update FOV parameters in the parameter table (one-way binding: model→UI display only).

        This updates the UI display to reflect the actual FOV range from the loaded metadata,
        while maintaining one-way binding (user input still updates model via _on_parameters_changed).

        Args:
            fov_start: Starting FOV index
            fov_end: Ending FOV index
        """
        defaults_data = {
            "fov_start": {"value": fov_start},
            "fov_end": {"value": fov_end},
            "batch_size": {"value": self._batch_size},
            "n_workers": {"value": self._n_workers},
        }
        df = pd.DataFrame.from_dict(defaults_data, orient="index")
        self._param_panel.set_parameters_df(df)
        logger.debug(
            "Updated FOV parameters in UI: fov_start=%d, fov_end=%d", fov_start, fov_end
        )

    # ------------------------------------------------------------------------
    # WORKER MANAGEMENT
    # ------------------------------------------------------------------------
    def _load_microscopy(self, path: Path) -> None:
        """Load microscopy metadata in background.

        Args:
            path: Path to the microscopy file to load
        """
        logger.info("Loading microscopy metadata from %s", path)
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
        """Handle microscopy metadata loaded.

        Args:
            metadata: Loaded microscopy metadata
        """
        logger.info("Microscopy metadata loaded")
        self._metadata = metadata
        self.load_microscopy_metadata(metadata)

        # Set internal FOV values based on metadata (one-way binding)
        if metadata and metadata.n_fovs > 0:
            self._fov_start = 0
            self._fov_end = metadata.n_fovs - 1
            # Update UI to reflect actual FOV range from metadata
            self._update_fov_parameters(self._fov_start, self._fov_end)

        filename = self._microscopy_path.name if self._microscopy_path else "ND2 file"

        self.microscopy_loading_finished.emit(True, f"{filename} loaded successfully")

    @Slot(str)
    def _on_microscopy_failed(self, message: str) -> None:
        """Handle microscopy loading failure.

        Args:
            message: Error message describing the failure
        """
        logger.error("Failed to load ND2: %s", message)
        filename = self._microscopy_path.name if self._microscopy_path else "ND2 file"

        self.microscopy_loading_finished.emit(
            False, f"Failed to load {filename}: {message}"
        )

    @Slot()
    def _on_loader_finished(self) -> None:
        """Handle microscopy loader thread finished."""
        logger.info("ND2 loader thread finished")
        self._microscopy_loader = None

    def _start_workflow(self) -> None:
        """Start the processing workflow.

        Validates all inputs and parameters, then creates and starts
        a background worker to execute the workflow.
        """
        # Validate prerequisites
        if not self._microscopy_path:
            return
        if not self._output_dir:
            return
        if self._pc_features and self._phase_channel is None:
            return
        if (
            self._phase_channel is None
            and not self._fl_features
            and not self._pc_features
        ):
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

        logger.debug("ProcessingContext built from user input: %s", context)
        logger.debug(
            "Workflow parameters: FOV range=%d-%d, batch_size=%d, n_workers=%d",
            self._fov_start,
            self._fov_end,
            self._batch_size,
            self._n_workers,
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

        self.workflow_started.emit()

    def _validate_parameters(self) -> bool:
        """Validate workflow parameters.

        Returns:
            bool: True if parameters are valid, False otherwise
        """
        if not self._metadata:
            return True  # Skip validation if no metadata

        n_fovs = getattr(self._metadata, "n_fovs", 0)

        if self._fov_start < 0:
            return False
        if self._fov_end < self._fov_start:
            return False
        if self._fov_end >= n_fovs:
            return False
        if self._batch_size <= 0:
            return False
        if self._n_workers <= 0:
            return False

        return True

    @Slot(bool, str)
    def _on_workflow_finished(self, success: bool, message: str) -> None:
        """Handle workflow completion.

        Args:
            success: Whether the workflow completed successfully
            message: Status message from the workflow
        """
        logger.info("Workflow finished (success=%s): %s", success, message)
        self.set_processing_active(False)
        self.set_process_enabled(True)

        self.workflow_finished.emit(success, message)

    def _clear_workflow_handle(self) -> None:
        """Clear workflow handle after completion.

        Called when the background thread finishes to clean up
        the worker handle and allow new workflow executions.
        """
        logger.info("Workflow thread finished")
        self._workflow_runner = None


# =============================================================================
# BACKGROUND WORKERS
# =============================================================================


class MicroscopyLoaderWorker(QObject):
    """Background worker for loading microscopy metadata.

    This worker handles loading microscopy files in a separate thread
    to prevent blocking the UI during file loading operations.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    loaded = Signal(object)  # Emitted when metadata is loaded successfully
    failed = Signal(str)  # Emitted when loading fails with error message
    finished = Signal()  # Signal to indicate work is complete

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, path: Path) -> None:
        """Initialize the microscopy loader worker.

        Args:
            path: Path to the microscopy file to load
        """
        super().__init__()
        self._path = path
        self._cancelled = False

    # ------------------------------------------------------------------------
    # WORKER CONTROL
    # ------------------------------------------------------------------------
    def cancel(self) -> None:
        """Mark this worker as cancelled.

        Sets a flag that will be checked during execution to
        allow for early termination of the loading process.
        """
        self._cancelled = True

    # ------------------------------------------------------------------------
    # WORKER EXECUTION
    # ------------------------------------------------------------------------
    def run(self) -> None:
        """Execute the microscopy loading.

        Loads the microscopy file and emits appropriate signals
        based on the result. Always emits the finished signal
        to ensure proper thread cleanup.
        """
        try:
            if self._cancelled:
                self.finished.emit()
                return

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
    """Background worker for running the processing workflow.

    This worker executes the complete image processing workflow
    in a separate thread to prevent UI blocking during long
    processing operations.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    finished = Signal(bool, str)  # Emitted when workflow completes (success, message)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
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
        """Initialize the workflow runner.

        Args:
            metadata: Microscopy metadata for the input file
            context: Processing context with channel and parameter configuration
            fov_start: Starting FOV index for processing
            fov_end: Ending FOV index for processing
            batch_size: Number of FOVs to process in each batch
            n_workers: Number of parallel worker threads
        """
        super().__init__()
        self._metadata = metadata
        self._context = ensure_context(context)
        self._fov_start = fov_start
        self._fov_end = fov_end
        self._batch_size = batch_size
        self._n_workers = n_workers
        self._cancel_event = threading.Event()

    # ------------------------------------------------------------------------
    # WORKER EXECUTION
    # ------------------------------------------------------------------------
    def run(self) -> None:
        """Execute the processing workflow.

        Runs the complete workflow and emits the finished signal
        with the result. Handles exceptions and cancellation
        gracefully.
        """
        try:
            # Check for cancellation before starting
            if self._cancel_event.is_set():
                logger.info("Workflow cancelled before execution")
                # Commented out cleanup to preserve partial results for debugging
                # self._cleanup_fov_folders()
                self.finished.emit(False, "Workflow cancelled")
                return

            success = run_complete_workflow(
                self._metadata,
                self._context,
                fov_start=self._fov_start,
                fov_end=self._fov_end,
                batch_size=self._batch_size,
                n_workers=self._n_workers,
                cancel_event=self._cancel_event,
            )

            # Check for cancellation after workflow completion
            if self._cancel_event.is_set():
                logger.info("Workflow was cancelled during execution")
                # Commented out cleanup to preserve partial results for debugging
                # self._cleanup_fov_folders()
                self.finished.emit(False, "Workflow cancelled")
                return

            if success:
                output_dir = self._context.output_dir or "output directory"
                message = f"Results saved to {output_dir}"
                self.finished.emit(True, message)
            else:  # pragma: no cover - defensive branch
                self.finished.emit(False, "Workflow reported failure")
        except Exception as exc:  # pragma: no cover - propagate to UI
            logger.exception("Workflow execution failed")
            self.finished.emit(False, f"Workflow error: {exc}")

    # ------------------------------------------------------------------------
    # WORKER CONTROL
    # ------------------------------------------------------------------------
    def cancel(self) -> None:
        """Cancel the workflow execution.

        Sets the cancellation event that will be checked by the
        underlying workflow implementation to allow for graceful
        termination of processing.
        """
        logger.info("Cancelling workflow execution")
        self._cancel_event.set()
        # Don't emit finished signal here - let the worker detect cancellation
        # and emit it naturally when it exits

    def _cleanup_fov_folders(self) -> None:
        """Clean up FOV folders created during processing when cancelled.

        Removes only the FOV directories that were being processed in this workflow
        to prevent partial results from being left behind.
        """
        try:
            output_dir = self._context.output_dir
            if not output_dir or not output_dir.exists():
                return

            logger.info("Cleaning up FOV folders after cancellation")

            # Remove only the FOV directories for the range being processed
            for fov_idx in range(self._fov_start, self._fov_end + 1):
                fov_dir = output_dir / f"fov_{fov_idx:03d}"
                if fov_dir.exists() and fov_dir.is_dir():
                    try:
                        import shutil

                        shutil.rmtree(fov_dir)
                        logger.debug("Removed FOV directory: %s", fov_dir)
                    except Exception as e:
                        logger.warning(
                            "Failed to remove FOV directory %s: %s", fov_dir, e
                        )

            # Also remove any processing_results.yaml if it exists
            results_file = output_dir / "processing_results.yaml"
            if results_file.exists():
                try:
                    results_file.unlink()
                    logger.debug("Removed processing results file: %s", results_file)
                except Exception as e:
                    logger.warning(
                        "Failed to remove results file %s: %s", results_file, e
                    )

        except Exception as e:
            logger.warning("Error during FOV folder cleanup: %s", e)
