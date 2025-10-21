"""Workflow wizard pages for pyama-air GUI."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from pyama_air.gui.workflow.main_wizard import WorkflowWizard

logger = logging.getLogger(__name__)


# =============================================================================
# FILE SELECTION PAGE
# =============================================================================


class FileSelectionPage(QWizardPage):
    """Page for selecting ND2 file and output directory."""

    def __init__(self, parent: WorkflowWizard) -> None:
        """Initialize the file selection page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("File Selection")
        self.setSubTitle("Select your ND2 microscopy file and output directory.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for file selection."""
        layout = QVBoxLayout(self)

        # ND2 file selection
        nd2_group = QGroupBox("ND2 File")
        nd2_layout = QFormLayout(nd2_group)

        self.nd2_path_edit = QLineEdit()
        self.nd2_path_edit.setPlaceholderText("Select ND2 file...")
        self.nd2_browse_btn = QPushButton("Browse...")
        self.nd2_browse_btn.clicked.connect(self._browse_nd2)

        nd2_file_layout = QHBoxLayout()
        nd2_file_layout.addWidget(self.nd2_path_edit)
        nd2_file_layout.addWidget(self.nd2_browse_btn)
        nd2_layout.addRow("ND2 File:", nd2_file_layout)

        layout.addWidget(nd2_group)

        # Output directory selection
        output_group = QGroupBox("Output Directory")
        output_layout = QFormLayout(output_group)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select output directory...")
        self.output_browse_btn = QPushButton("Browse...")
        self.output_browse_btn.clicked.connect(self._browse_output)

        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.output_path_edit)
        output_dir_layout.addWidget(self.output_browse_btn)
        output_layout.addRow("Output Directory:", output_dir_layout)

        layout.addWidget(output_group)

        # Channel info display
        self.channel_info = QLabel("No file selected")
        self.channel_info.setWordWrap(True)
        self.channel_info.setStyleSheet("QLabel { color: gray; }")
        layout.addWidget(self.channel_info)

        layout.addStretch()

    @Slot()
    def _browse_nd2(self) -> None:
        """Browse for ND2 file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ND2 File", "", "ND2 Files (*.nd2);;All Files (*)"
        )
        if file_path:
            self._page_data.nd2_path = Path(file_path)
            self.nd2_path_edit.setText(str(self._page_data.nd2_path))
            self._load_metadata()

    @Slot()
    def _browse_output(self) -> None:
        """Browse for output directory."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
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

    def __init__(self, parent: WorkflowWizard) -> None:
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
        self.pc_group = QGroupBox("Phase Contrast Channel")
        self.pc_layout = QVBoxLayout(self.pc_group)

        self.pc_radios: list[QRadioButton] = []
        self.pc_layout.addWidget(QLabel("Select the phase contrast channel:"))

        layout.addWidget(self.pc_group)

        # Fluorescence channels selection
        self.fl_group = QGroupBox("Fluorescence Channels")
        self.fl_layout = QVBoxLayout(self.fl_group)

        self.fl_checkboxes: list[QCheckBox] = []
        self.fl_layout.addWidget(
            QLabel("Select fluorescence channels (check all that apply):")
        )

        layout.addWidget(self.fl_group)

        layout.addStretch()

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
        return len(self._page_data.fl_channels) > 0


# =============================================================================
# FEATURE SELECTION PAGE
# =============================================================================


class FeatureSelectionPage(QWizardPage):
    """Page for selecting features for each channel."""

    def __init__(self, parent: WorkflowWizard) -> None:
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
        self.pc_group = QGroupBox("Phase Contrast Features")
        self.pc_layout = QVBoxLayout(self.pc_group)
        self.scroll_layout.addWidget(self.pc_group)

        # Fluorescence features
        self.fl_group = QGroupBox("Fluorescence Features")
        self.fl_layout = QVBoxLayout(self.fl_group)
        self.scroll_layout.addWidget(self.fl_group)

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

        # Fluorescence features
        for fl_channel in sorted(self._page_data.fl_channels):
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
        if checked:
            self._page_data.fl_feature_map[channel].add(feature)
        else:
            self._page_data.fl_feature_map[channel].discard(feature)

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        return len(self._page_data.pc_features) > 0 and any(
            self._page_data.fl_feature_map.values()
        )


# =============================================================================
# PARAMETER CONFIGURATION PAGE
# =============================================================================


class ParameterConfigurationPage(QWizardPage):
    """Page for configuring workflow parameters."""

    def __init__(self, parent: WorkflowWizard) -> None:
        """Initialize the parameter configuration page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Parameter Configuration")
        self.setSubTitle("Configure workflow execution parameters.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for parameter configuration."""
        layout = QFormLayout(self)

        # Time units
        self.time_units_combo = QComboBox()
        self.time_units_combo.addItems(["hours", "minutes", "seconds"])
        self.time_units_combo.setCurrentText("hours")
        layout.addRow("Time Units:", self.time_units_combo)

        # FOV range
        self.fov_start_spin = QSpinBox()
        self.fov_start_spin.setMinimum(0)
        self.fov_start_spin.setValue(0)
        layout.addRow("FOV Start:", self.fov_start_spin)

        self.fov_end_spin = QSpinBox()
        self.fov_end_spin.setMinimum(0)
        self.fov_end_spin.setValue(0)
        layout.addRow("FOV End:", self.fov_end_spin)

        # Batch size
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setMinimum(1)
        self.batch_size_spin.setMaximum(100)
        self.batch_size_spin.setValue(2)
        layout.addRow("Batch Size:", self.batch_size_spin)

        # Number of workers
        self.n_workers_spin = QSpinBox()
        self.n_workers_spin.setMinimum(1)
        self.n_workers_spin.setMaximum(32)
        self.n_workers_spin.setValue(1)
        layout.addRow("Number of Workers:", self.n_workers_spin)

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
# EXECUTION PAGE
# =============================================================================


class ExecutionPage(QWizardPage):
    """Page for executing the workflow."""

    def __init__(self, parent: WorkflowWizard) -> None:
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

        # Configuration summary
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # Execute button
        self.execute_btn = QPushButton("Execute Workflow")
        self.execute_btn.clicked.connect(self._execute_workflow)
        layout.addWidget(self.execute_btn)

        # Progress/status
        self.status_label = QLabel("Ready to execute")
        layout.addWidget(self.status_label)

        layout.addStretch()

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
        # This would integrate with the actual workflow execution
        # For now, just show a placeholder
        self.status_label.setText("Workflow execution would start here...")
        self.execute_btn.setEnabled(False)
