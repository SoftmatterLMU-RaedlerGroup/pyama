"""Workflow wizard pages for pyama-air GUI."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from pyama_core.io import MicroscopyMetadata
from pyama_core.processing.workflow import ensure_context, run_complete_workflow
from pyama_core.types.processing import ChannelSelection, Channels, ProcessingContext

logger = logging.getLogger(__name__)


# =============================================================================
# FILE SELECTION PAGE
# =============================================================================


class FileSelectionPage(QWizardPage):
    """Page for selecting ND2 file and output directory."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the file selection page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("File Selection")
        self.setSubTitle("Select your microscopy file (ND2, CZI, or OME-TIFF) and output directory.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for file selection."""
        layout = QVBoxLayout(self)

        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout(file_group)

        # ND2 file selection
        nd2_row = QHBoxLayout()
        nd2_row.addWidget(QLabel("Microscopy File:"))
        nd2_row.addStretch()
        self.nd2_browse_btn = QPushButton("Browse")
        self.nd2_browse_btn.clicked.connect(self._browse_nd2)
        nd2_row.addWidget(self.nd2_browse_btn)
        file_layout.addLayout(nd2_row)

        self.nd2_path_edit = QLineEdit()
        self.nd2_path_edit.setPlaceholderText("Select microscopy file (ND2, CZI, or OME-TIFF)...")
        self.nd2_path_edit.setReadOnly(True)
        file_layout.addWidget(self.nd2_path_edit)

        # Output directory selection
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output Directory:"))
        output_row.addStretch()
        self.output_browse_btn = QPushButton("Browse")
        self.output_browse_btn.clicked.connect(self._browse_output)
        output_row.addWidget(self.output_browse_btn)
        file_layout.addLayout(output_row)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select output directory...")
        self.output_path_edit.setReadOnly(True)
        file_layout.addWidget(self.output_path_edit)

        layout.addWidget(file_group)

        # File information group
        info_group = QGroupBox("File Information")
        info_layout = QVBoxLayout(info_group)

        self.channel_info = QLabel("No file selected")
        self.channel_info.setWordWrap(True)
        self.channel_info.setStyleSheet("QLabel { color: gray; }")
        info_layout.addWidget(self.channel_info)

        layout.addWidget(info_group)

    @Slot()
    def _browse_nd2(self) -> None:
        """Browse for microscopy file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Microscopy File",
            "",
            "Microscopy Files (*.nd2 *.czi *.ome.tiff);;ND2 Files (*.nd2);;CZI Files (*.czi);;OME-TIFF Files (*.ome.tiff);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._page_data.nd2_path = Path(file_path)
            self.nd2_path_edit.setText(str(self._page_data.nd2_path))
            self._load_metadata()

    @Slot()
    def _browse_output(self) -> None:
        """Browse for output directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if dir_path:
            self._page_data.output_dir = Path(dir_path)
            self.output_path_edit.setText(str(self._page_data.output_dir))

    def _load_metadata(self) -> None:
        """Load metadata from ND2 file."""
        if not self._page_data.nd2_path:
            return

        try:
            from pyama_core.io import load_microscopy_file

            image, metadata = load_microscopy_file(self._page_data.nd2_path)
            if hasattr(image, "close"):
                try:
                    image.close()
                except Exception:
                    pass

            self._page_data.metadata = metadata

            # Update channel info
            channel_names = metadata.channel_names or [
                f"C{i}" for i in range(metadata.n_channels)
            ]
            self.wizard._channel_names = channel_names

            info_text = f"Channels: {len(channel_names)}\n"
            info_text += f"FOVs: {metadata.n_fovs}\n"
            info_text += f"Frames: {metadata.n_frames}\n\n"
            info_text += "Channel Names:\n"
            for i, name in enumerate(channel_names):
                info_text += f"  [{i}] {name or f'C{i}'}\n"

            self.channel_info.setText(info_text)
            self.channel_info.setStyleSheet("")

            # Set default output directory
            if not self._page_data.output_dir:
                self._page_data.output_dir = self._page_data.nd2_path.parent
                self.output_path_edit.setText(str(self._page_data.output_dir))

        except Exception as exc:
            logger.error("Failed to load ND2 file: %s", exc)
            self.channel_info.setText(f"Error loading file: {exc}")
            self.channel_info.setStyleSheet("QLabel { color: red; }")

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        if not self._page_data.nd2_path or not self._page_data.nd2_path.exists():
            return False
        if not self._page_data.output_dir:
            return False
        return True


# =============================================================================
# CHANNEL CONFIGURATION PAGE
# =============================================================================


class ChannelConfigurationPage(QWizardPage):
    """Page for configuring phase contrast and fluorescence channels."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the channel configuration page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Channel Configuration")
        self.setSubTitle("Select phase contrast and fluorescence channels.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for channel configuration."""
        layout = QVBoxLayout(self)

        # Phase contrast channel selection
        pc_group = QGroupBox("Phase Contrast Channel")
        self.pc_layout = QVBoxLayout(pc_group)

        self.pc_radios: list[QRadioButton] = []

        layout.addWidget(pc_group)

        # Fluorescence channels selection
        fl_group = QGroupBox("Fluorescence Channels")
        self.fl_layout = QVBoxLayout(fl_group)

        self.fl_checkboxes: list[QCheckBox] = []

        layout.addWidget(fl_group)

    def initializePage(self) -> None:
        """Initialize the page with channel data."""
        if not self.wizard._channel_names:
            return

        # Clear existing widgets
        for radio in self.pc_radios:
            radio.deleteLater()
        for checkbox in self.fl_checkboxes:
            checkbox.deleteLater()
        self.pc_radios.clear()
        self.fl_checkboxes.clear()

        # Create phase contrast radio buttons
        for i, name in enumerate(self.wizard._channel_names):
            radio = QRadioButton(f"[{i}] {name or f'C{i}'}")
            radio.setProperty("channel_index", i)
            radio.toggled.connect(self._on_pc_channel_changed)
            self.pc_radios.append(radio)
            self.pc_layout.addWidget(radio)

        # Select first channel by default
        if self.pc_radios:
            self.pc_radios[0].setChecked(True)

        # Create fluorescence checkboxes
        for i, name in enumerate(self.wizard._channel_names):
            checkbox = QCheckBox(f"[{i}] {name or f'C{i}'}")
            checkbox.setProperty("channel_index", i)
            checkbox.toggled.connect(self._on_fl_channel_changed)
            self.fl_checkboxes.append(checkbox)
            self.fl_layout.addWidget(checkbox)

    @Slot(bool)
    def _on_pc_channel_changed(self, checked: bool) -> None:
        """Handle phase contrast channel selection."""
        if checked:
            sender = self.sender()
            self._page_data.pc_channel = sender.property("channel_index")

    @Slot(bool)
    def _on_fl_channel_changed(self, checked: bool) -> None:
        """Handle fluorescence channel selection."""
        sender = self.sender()
        channel = sender.property("channel_index")
        if checked:
            self._page_data.fl_channels.add(channel)
        else:
            self._page_data.fl_channels.discard(channel)

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        # Allow proceeding even if no fluorescence channels are selected
        return True


# =============================================================================
# FEATURE SELECTION PAGE
# =============================================================================


class FeatureSelectionPage(QWizardPage):
    """Page for selecting features for each channel."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the feature selection page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Feature Selection")
        self.setSubTitle("Select features to extract for each channel.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for feature selection."""
        layout = QVBoxLayout(self)

        # Create scroll area for features
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_widget)

        # Phase contrast features
        pc_group = QGroupBox("Phase Contrast Features")
        self.pc_layout = QVBoxLayout(pc_group)
        self.scroll_layout.addWidget(pc_group)

        # Fluorescence features
        fl_group = QGroupBox("Fluorescence Features")
        self.fl_layout = QVBoxLayout(fl_group)
        self.scroll_layout.addWidget(fl_group)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def initializePage(self) -> None:
        """Initialize the page with feature data."""
        # Clear existing widgets
        self._clear_layout(self.pc_layout)
        self._clear_layout(self.fl_layout)

        # Phase contrast features
        self.pc_layout.addWidget(
            QLabel(f"Features for PC channel [{self._page_data.pc_channel}]:")
        )

        for feature in self.wizard._pc_features:
            checkbox = QCheckBox(feature)
            checkbox.setChecked(True)  # Default to selected
            checkbox.toggled.connect(self._on_pc_feature_changed)
            self.pc_layout.addWidget(checkbox)
            # Initialize feature in the set since checkbox is checked by default
            self._page_data.pc_features.add(feature)

        # Fluorescence features
        for fl_channel in sorted(self._page_data.fl_channels):
            # Initialize feature set for this channel if it doesn't exist
            if fl_channel not in self._page_data.fl_feature_map:
                self._page_data.fl_feature_map[fl_channel] = set()

            fl_widget = QWidget()
            fl_widget_layout = QVBoxLayout(fl_widget)
            fl_widget_layout.addWidget(
                QLabel(f"Features for FL channel [{fl_channel}]:")
            )

            for feature in self.wizard._fl_features:
                checkbox = QCheckBox(feature)
                checkbox.setChecked(True)  # Default to selected
                checkbox.setProperty("channel", fl_channel)
                checkbox.toggled.connect(self._on_fl_feature_changed)
                fl_widget_layout.addWidget(checkbox)
                # Initialize feature in the set since checkbox is checked by default
                self._page_data.fl_feature_map[fl_channel].add(feature)

            self.fl_layout.addWidget(fl_widget)

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        """Clear all widgets from a layout."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    @Slot(bool)
    def _on_pc_feature_changed(self, checked: bool) -> None:
        """Handle phase contrast feature selection."""
        sender = self.sender()
        feature = sender.text()
        if checked:
            self._page_data.pc_features.add(feature)
        else:
            self._page_data.pc_features.discard(feature)

    @Slot(bool)
    def _on_fl_feature_changed(self, checked: bool) -> None:
        """Handle fluorescence feature selection."""
        sender = self.sender()
        feature = sender.text()
        channel = sender.property("channel")
        
        # Initialize feature set for this channel if it doesn't exist
        if channel not in self._page_data.fl_feature_map:
            self._page_data.fl_feature_map[channel] = set()
        
        if checked:
            self._page_data.fl_feature_map[channel].add(feature)
        else:
            self._page_data.fl_feature_map[channel].discard(feature)

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        # Allow proceeding even if no features are selected
        return True


# =============================================================================
# PARAMETER CONFIGURATION PAGE
# =============================================================================


class ParameterConfigurationPage(QWizardPage):
    """Page for configuring workflow parameters."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the parameter configuration page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Parameter Configuration")
        self.setSubTitle("Configure workflow execution parameters.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for parameter configuration."""
        layout = QVBoxLayout(self)

        # Time and FOV configuration group
        time_fov_group = QGroupBox("Time & FOV Configuration")
        time_fov_layout = QFormLayout(time_fov_group)

        # Time units
        self.time_units_combo = QComboBox()
        self.time_units_combo.addItems(["hours", "minutes", "seconds"])
        self.time_units_combo.setCurrentText("hours")
        time_fov_layout.addRow("Time Units:", self.time_units_combo)

        # FOV range
        self.fov_start_spin = QSpinBox()
        self.fov_start_spin.setMinimum(0)
        self.fov_start_spin.setValue(0)
        time_fov_layout.addRow("FOV Start:", self.fov_start_spin)

        self.fov_end_spin = QSpinBox()
        self.fov_end_spin.setMinimum(0)
        self.fov_end_spin.setValue(0)
        time_fov_layout.addRow("FOV End:", self.fov_end_spin)

        layout.addWidget(time_fov_group)

        # Execution parameters group
        execution_group = QGroupBox("Execution Parameters")
        execution_layout = QFormLayout(execution_group)

        # Batch size
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setMinimum(1)
        self.batch_size_spin.setMaximum(100)
        self.batch_size_spin.setValue(2)
        execution_layout.addRow("Batch Size:", self.batch_size_spin)

        # Number of workers
        self.n_workers_spin = QSpinBox()
        self.n_workers_spin.setMinimum(1)
        self.n_workers_spin.setMaximum(32)
        self.n_workers_spin.setValue(1)
        execution_layout.addRow("Number of Workers:", self.n_workers_spin)

        layout.addWidget(execution_group)

    def initializePage(self) -> None:
        """Initialize the page with metadata."""
        if self._page_data.metadata:
            max_fov = max(self._page_data.metadata.n_fovs - 1, 0)
            self.fov_end_spin.setMaximum(max_fov)
            self.fov_end_spin.setValue(max_fov)

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        self._page_data.time_units = self.time_units_combo.currentText()
        self._page_data.fov_start = self.fov_start_spin.value()
        self._page_data.fov_end = self.fov_end_spin.value()
        self._page_data.batch_size = self.batch_size_spin.value()
        self._page_data.n_workers = self.n_workers_spin.value()
        return self._page_data.fov_start <= self._page_data.fov_end


# =============================================================================
# WORKFLOW WORKER
# =============================================================================


class WorkflowWorker(QObject):
    """Worker for running workflow execution in background thread."""

    finished = Signal(bool, str)  # success, message

    def __init__(
        self,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        fov_start: int,
        fov_end: int,
        batch_size: int,
        n_workers: int,
    ) -> None:
        """Initialize the workflow worker.

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

    def run(self) -> None:
        """Run the workflow execution."""
        try:
            # Check for cancellation before starting
            if self._cancel_event.is_set():
                logger.info(
                    "Workflow cancelled before execution (fovs=%d-%d)",
                    self._fov_start,
                    self._fov_end,
                )
                self.finished.emit(False, "Workflow cancelled")
                return

            logger.info(
                "Workflow execution started (fovs=%d-%d, batch_size=%d, workers=%d, output_dir=%s)",
                self._fov_start,
                self._fov_end,
                self._batch_size,
                self._n_workers,
                self._context.output_dir,
            )

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
                logger.info(
                    "Workflow was cancelled during execution (fovs=%d-%d)",
                    self._fov_start,
                    self._fov_end,
                )
                self.finished.emit(False, "Workflow cancelled")
                return

            if success:
                output_dir = self._context.output_dir or "output directory"
                message = f"Results saved to {output_dir}"
                self.finished.emit(True, message)
            else:
                self.finished.emit(False, "Workflow reported failure")
        except Exception as exc:
            logger.exception("Workflow execution failed")
            self.finished.emit(False, f"Workflow error: {exc}")

    def cancel(self) -> None:
        """Cancel the workflow execution."""
        logger.info(
            "Cancelling workflow execution (fovs=%d-%d, output_dir=%s)",
            self._fov_start,
            self._fov_end,
            self._context.output_dir,
        )
        self._cancel_event.set()


# =============================================================================
# EXECUTION PAGE
# =============================================================================


class ExecutionPage(QWizardPage):
    """Page for executing the workflow."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the execution page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Execute Workflow")
        self.setSubTitle("Review configuration and execute the workflow.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for execution."""
        layout = QVBoxLayout(self)

        # Configuration summary group
        summary_group = QGroupBox("Configuration Summary")
        summary_layout = QVBoxLayout(summary_group)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)

        layout.addWidget(summary_group)

        # Action group
        action_group = QGroupBox("Execution")
        action_layout = QVBoxLayout(action_group)

        # Execute button
        self.execute_btn = QPushButton("Execute Workflow")
        self.execute_btn.clicked.connect(self._execute_workflow)
        action_layout.addWidget(self.execute_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar)

        # Progress/status
        self.status_label = QLabel("Ready to execute")
        action_layout.addWidget(self.status_label)

        layout.addWidget(action_group)

        # Worker thread tracking
        self._worker_thread: QThread | None = None
        self._worker: WorkflowWorker | None = None

    def initializePage(self) -> None:
        """Initialize the page with configuration summary."""
        config = self.wizard.get_workflow_config()
        if not config:
            self.summary_label.setText("Error: Invalid configuration")
            return

        # Build summary text
        summary = "Configuration Summary:\n\n"
        summary += f"Output Directory: {config.output_dir}\n"
        summary += f"PC Channel: {config.pc_channel}\n"
        summary += f"PC Features: {', '.join(config.pc_features)}\n"
        summary += f"FL Channels: {len(config.fl_channels)}\n"
        for fl_channel in sorted(config.fl_channels):
            features = config.fl_feature_map.get(fl_channel, set())
            summary += f"  Channel {fl_channel}: {', '.join(features)}\n"
        summary += f"Time Units: {config.time_units}\n"

        self.summary_label.setText(summary)

    @Slot()
    def _execute_workflow(self) -> None:
        """Execute the workflow."""
        config = self.wizard.get_workflow_config()
        if not config:
            self.status_label.setText("Error: Invalid configuration")
            return

        if not config.metadata:
            self.status_label.setText("Error: No metadata available. Please reload the file.")
            return

        # Ensure metadata has file_path set correctly
        if not hasattr(config.metadata, "file_path") or config.metadata.file_path is None:
            # Set file_path from nd2_path if missing
            config.metadata.file_path = config.nd2_path

        try:
            self.status_label.setText("Starting workflow...")
            self.execute_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress

            # Build ProcessingContext from WorkflowConfig
            # PC channel is required for segmentation even if no features are selected
            pc_selection = (
                ChannelSelection(
                    channel=int(config.pc_channel),
                    features=list(config.pc_features),
                )
                if config.pc_channel is not None
                else None
            )
            fl_selections = [
                ChannelSelection(channel=int(channel), features=list(features))
                for channel, features in sorted(config.fl_feature_map.items())
            ]

            context = ProcessingContext(
                output_dir=config.output_dir,
                channels=Channels(pc=pc_selection, fl=fl_selections),
                params={},  # Use default parameters
                time_units=config.time_units,
            )

            # Resolve FOV end if needed
            resolved_fov_end = (
                config.metadata.n_fovs - 1
                if config.fov_end >= config.metadata.n_fovs
                else config.fov_end
            )

            logger.info(
                "Starting workflow for %s -> %s (fovs=%d-%d, batch_size=%d, workers=%d)",
                config.nd2_path.name,
                config.output_dir,
                config.fov_start,
                resolved_fov_end,
                config.batch_size,
                config.n_workers,
            )

            # Create and start worker
            self._worker_thread = QThread()
            self._worker = WorkflowWorker(
                metadata=config.metadata,
                context=context,
                fov_start=config.fov_start,
                fov_end=resolved_fov_end,
                batch_size=config.batch_size,
                n_workers=config.n_workers,
            )
            self._worker.moveToThread(self._worker_thread)
            self._worker_thread.started.connect(self._worker.run)
            self._worker.finished.connect(self._on_workflow_finished)
            self._worker.finished.connect(self._worker_thread.quit)
            self._worker_thread.finished.connect(self._worker_thread.deleteLater)

            self._worker_thread.start()

            # Emit wizard signal
            self.wizard.workflow_started.emit()

        except Exception as exc:
            error_msg = f"Workflow failed: {exc}"
            self.status_label.setText(error_msg)
            self.wizard.workflow_finished.emit(False, error_msg)
            logger.error("Workflow execution failed: %s", exc)
            self.progress_bar.setVisible(False)
            self.execute_btn.setEnabled(True)

    @Slot(bool, str)
    def _on_workflow_finished(self, success: bool, message: str) -> None:
        """Handle workflow completion."""
        self.progress_bar.setVisible(False)
        self.execute_btn.setEnabled(True)

        if success:
            self.status_label.setText(f"Workflow completed: {message}")
        else:
            self.status_label.setText(f"Workflow failed: {message}")

        # Emit signal for wizard
        self.wizard.workflow_finished.emit(success, message)
