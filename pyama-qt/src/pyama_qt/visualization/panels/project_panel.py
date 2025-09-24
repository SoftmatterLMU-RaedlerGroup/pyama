"""Project loader panel for the visualization application."""

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QFileDialog,
    QSpinBox,
    QCheckBox,
    QMessageBox,
    QProgressBar,
    QTextEdit,
)
from PySide6.QtCore import Signal
from pathlib import Path

from pyama_qt.visualization.state import VisualizationState
from pyama_qt.ui import BasePanel
import logging

logger = logging.getLogger(__name__)


class ProjectPanel(BasePanel[VisualizationState]):
    """Panel for loading and displaying FOV data from folders."""

    project_load_requested = Signal(Path)  # Emitted when project load is requested
    visualization_requested = Signal(int, list)  # FOV index, selected channels

    def build(self) -> None:
        layout = QVBoxLayout(self)

        # Project loading section
        load_group = QGroupBox("Load Data Folder")
        load_layout = QVBoxLayout(load_group)

        self.load_button = QPushButton("Load Folder")
        self.load_button.clicked.connect(self._on_load_folder_clicked)
        self.load_button.setToolTip("Load a folder containing FOV subdirectories")
        load_layout.addWidget(self.load_button)

        # Project details text area
        self.project_details_text = QTextEdit()
        self.project_details_text.setMaximumHeight(150)
        self.project_details_text.setReadOnly(True)
        self.project_details_text.setStyleSheet(
            "font-family: monospace; font-size: 10px;"
        )
        load_layout.addWidget(self.project_details_text)

        layout.addWidget(load_group, 1)

        # Selection controls
        selection_group = QGroupBox("Visualization Settings")
        selection_layout = QVBoxLayout(selection_group)

        # FOV selection
        fov_row = QHBoxLayout()
        self.fov_spinbox = QSpinBox()
        self.fov_spinbox.setMinimum(0)
        self.fov_spinbox.setMaximum(999)
        self.fov_spinbox.setEnabled(False)
        self.fov_spinbox.valueChanged.connect(self._on_fov_changed)

        self.fov_max_label = QLabel("/ 0")
        self.fov_max_label.setStyleSheet("color: gray;")

        fov_row.addWidget(QLabel("FOV:"))
        fov_row.addStretch()
        fov_row.addWidget(self.fov_spinbox)
        fov_row.addWidget(self.fov_max_label)

        selection_layout.addLayout(fov_row)

        # Channel selection section
        channels_label = QLabel("Channels to load:")
        channels_label.setStyleSheet("font-weight: bold;")
        selection_layout.addWidget(channels_label)

        # Phase contrast channel
        self.pc_checkbox = QCheckBox("Phase Contrast")
        self.pc_checkbox.setChecked(True)
        self.pc_checkbox.setEnabled(False)
        selection_layout.addWidget(self.pc_checkbox)

        # Fluorescence channels (dynamic)
        self.fl_checkboxes = []
        self.fl_layout = QVBoxLayout()
        selection_layout.addLayout(self.fl_layout)

        # Segmentation channel
        self.seg_checkbox = QCheckBox("Segmentation")
        self.seg_checkbox.setChecked(False)
        self.seg_checkbox.setEnabled(False)
        selection_layout.addWidget(self.seg_checkbox)

        # Visualization button
        self.visualize_button = QPushButton("Start Visualization")
        self.visualize_button.clicked.connect(self._on_visualize_clicked)
        self.visualize_button.setEnabled(False)
        selection_layout.addWidget(self.visualize_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        selection_layout.addWidget(self.progress_bar)

        layout.addWidget(selection_group, 1)

        # Initially disable selection group
        selection_group.setEnabled(False)
        self.selection_group = selection_group

    def bind(self) -> None:
        # No additional bindings needed for this panel
        pass

    def set_state(self, state: VisualizationState) -> None:
        super().set_state(state)

        if state.project_data:
            self._update_project_ui(state)

        # Update progress bar
        if state.is_loading:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.progress_bar.setFormat(state.status_message)
        else:
            self.progress_bar.setVisible(False)

    # Event handlers -------------------------------------------------------
    def _on_load_folder_clicked(self) -> None:
        """Handle load folder button click."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Data Folder",
            "",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self.project_load_requested.emit(Path(directory))

    def _on_fov_changed(self) -> None:
        """Handle FOV spinbox value change."""
        # Reset visualization button when FOV changes
        self.visualize_button.setText("Start Visualization")
        self.visualize_button.setEnabled(True)

    def _on_visualize_clicked(self) -> None:
        """Handle visualization button click."""
        if not self._state or not self._state.project_data:
            return

        # Get current selections
        fov_idx = self.fov_spinbox.value()
        selected_channels = self._get_selected_channels()

        if not selected_channels:
            QMessageBox.warning(
                self,
                "No Channels Selected",
                "Please select at least one channel to visualize.",
            )
            return

        # Check if selected FOV exists
        if fov_idx not in self._state.project_data["fov_data"]:
            QMessageBox.warning(
                self,
                "Invalid FOV",
                f"FOV {fov_idx} does not exist in the loaded project.",
            )
            return

        # Emit visualization request
        self.visualization_requested.emit(fov_idx, selected_channels)

        # Update button state
        self.visualize_button.setText("Loading...")
        self.visualize_button.setEnabled(False)

    # Private methods -------------------------------------------------------
    def _update_project_ui(self, state: VisualizationState) -> None:
        """Update the UI with loaded project data."""
        project_data = state.project_data
        if not project_data:
            return

        # Show project details
        self._show_project_details(project_data)

        # Update FOV range
        max_fov = (
            max(project_data["fov_data"].keys()) if project_data["fov_data"] else 0
        )
        self.fov_spinbox.setMaximum(max_fov)
        self.fov_spinbox.setEnabled(True)
        self.fov_max_label.setText(f"/ {max_fov}")

        # Setup channel checkboxes
        self._setup_channel_checkboxes(state.available_channels)

        # Enable selection group
        self.selection_group.setEnabled(True)
        self.visualize_button.setEnabled(True)

    def _show_project_details(self, project_data: dict) -> None:
        """Display a summary of the loaded project data."""
        details = []

        # Project path
        project_path = project_data.get("project_path", "Unknown")
        details.append(f"📁 Project Path: {project_path}")

        # Basic info
        n_fov = project_data.get("n_fov", 0)
        microscopy_file = project_data.get("microscopy_file", "Unknown")
        details.append(f"🔬 Source ND2: {microscopy_file}")
        details.append(f"📊 FOVs: {n_fov}")

        # Processing status
        has_project_file = project_data.get("has_project_file", False)
        processing_status = project_data.get("processing_status", "unknown")
        status_icon = "✅" if processing_status == "completed" else "⚠️"

        if has_project_file:
            details.append(f"{status_icon} Status: {processing_status.title()}")
        else:
            details.append("ℹ️ Status: No project file found")

        # Available data types
        if project_data.get("fov_data"):
            first_fov = next(iter(project_data["fov_data"].values()))
            data_types = list(first_fov.keys())
            details.append("📋 Available Data:")
            details.extend([f"   • {dt}" for dt in data_types])

        # Display in text widget
        details_text = "\n".join(details)
        self.project_details_text.setPlainText(details_text)

    def _setup_channel_checkboxes(self, available_channels: list[str]) -> None:
        """Setup channel checkboxes based on available channels."""
        # Clear existing fluorescence checkboxes
        for checkbox in self.fl_checkboxes:
            checkbox.deleteLater()
        self.fl_checkboxes.clear()

        # Enable/disable phase contrast
        self.pc_checkbox.setEnabled("pc" in available_channels)
        if "pc" not in available_channels:
            self.pc_checkbox.setChecked(False)

        # Create fluorescence channel checkboxes
        fl_channels = [ch for ch in available_channels if ch.startswith("fl_")]
        for channel in sorted(fl_channels):
            checkbox = QCheckBox(f"Fluorescence {channel.split('_')[1]}")
            checkbox.setChecked(True)
            self.fl_checkboxes.append(checkbox)
            self.fl_layout.addWidget(checkbox)

        # Enable/disable segmentation
        has_seg = any("seg" in ch for ch in available_channels if ch in ["seg"])
        self.seg_checkbox.setEnabled(has_seg)
        if not has_seg:
            self.seg_checkbox.setChecked(False)

    def _get_selected_channels(self) -> list[str]:
        """Get list of selected channels for visualization."""
        selected_channels = []

        # Add phase contrast if selected and available
        if self.pc_checkbox.isChecked() and self.pc_checkbox.isEnabled():
            selected_channels.append("pc")

        # Add selected fluorescence channels
        for i, checkbox in enumerate(self.fl_checkboxes):
            if checkbox.isChecked():
                selected_channels.append(f"fl_{i + 1}")

        # Add segmentation if selected and available
        if self.seg_checkbox.isChecked() and self.seg_checkbox.isEnabled():
            selected_channels.append("seg")

        return selected_channels
