"""
Project loader widget for the visualization application.
This widget provides a simplified interface for loading FOV data from folders.
"""

from PySide6.QtWidgets import (
    QWidget,
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

from pyama_core.io.result_loader import discover_processing_results
import logging

logger = logging.getLogger(__name__)


class ProjectPanel(QWidget):
    """Widget for loading and displaying FOV data from folders."""

    project_loaded = Signal(dict)  # Emitted when project is successfully loaded
    visualization_requested = Signal(
        int,
        list,  # FOV index, list of selected channels
    )  # Emitted when visualization is requested for an FOV

    def __init__(self):
        super().__init__()
        self.current_project = None
        self.available_channels = []
        self.visualization_started = False
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)

        # Project loading section
        load_group = QGroupBox("Load Data Folder")
        load_layout = QVBoxLayout(load_group)

        self.load_button = QPushButton("Load Folder")
        self.load_button.clicked.connect(self.load_folder_dialog)
        self.load_button.setToolTip("Load a folder containing FOV subdirectories")
        load_layout.addWidget(self.load_button)

        # Project details text area (initially visible)
        self.project_details_text = QTextEdit()
        self.project_details_text.setMaximumHeight(150)
        self.project_details_text.setReadOnly(True)
        self.project_details_text.setVisible(True)
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
        self.fov_spinbox.valueChanged.connect(self.on_fov_changed)

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

        # Phase contrast channel (always available)
        self.pc_checkbox = QCheckBox("Phase Contrast")
        self.pc_checkbox.setChecked(True)
        self.pc_checkbox.setEnabled(False)
        selection_layout.addWidget(self.pc_checkbox)

        # Fluorescence channels (dynamic based on project)
        self.fl_checkboxes = []
        self.fl_layout = QVBoxLayout()
        selection_layout.addLayout(self.fl_layout)

        # Segmentation data checkbox
        self.seg_checkbox = QCheckBox("Segmentation")
        self.seg_checkbox.setChecked(False)
        self.seg_checkbox.setEnabled(False)
        selection_layout.addWidget(self.seg_checkbox)

        # Visualization button
        button_layout = QHBoxLayout()
        self.visualize_button = QPushButton("Start Visualization")
        self.visualize_button.clicked.connect(self.on_visualize_clicked)
        self.visualize_button.setEnabled(False)
        button_layout.addWidget(self.visualize_button)

        selection_layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        selection_layout.addWidget(self.progress_bar)

        layout.addWidget(selection_group, 1)

        # Initially disable selection group
        selection_group.setEnabled(False)
        self.selection_group = selection_group

    def load_folder_dialog(self):
        """Open dialog to select data folder."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setWindowTitle("Select Data Folder")

        if dialog.exec():
            selected_dirs = dialog.selectedFiles()
            if selected_dirs:
                self.load_folder(Path(selected_dirs[0]))

    def load_folder(self, folder_path: Path):
        """
        Load data from folder.

        Args:
            folder_path: Path to the data folder containing FOV subdirectories
        """
        try:
            logger.info(f"Loading folder: {folder_path}")

            # Discover processing results
            project_data = discover_processing_results(folder_path)

            self.current_project = project_data
            logger.info(
                f"Successfully loaded project with {project_data['n_fov']} FOVs"
            )

            # Update UI with project data
            self.update_project_ui(project_data)

            # Enable selection controls
            self.selection_group.setEnabled(True)

            # Emit signal
            self.project_loaded.emit(project_data)

        except Exception as e:
            logger.error(f"Failed to load data from {folder_path}: {str(e)}")
            QMessageBox.critical(
                self,
                "Error Loading Data",
                f"Failed to load data from {folder_path}:\\n{str(e)}",
            )

    def update_project_ui(self, project_data: dict):
        """Update the UI with loaded project data."""
        # Show project details
        self.show_project_details(project_data)

        # Update FOV range
        max_fov = (
            max(project_data["fov_data"].keys()) if project_data["fov_data"] else 0
        )
        self.fov_spinbox.setMaximum(max_fov)
        self.fov_spinbox.setEnabled(True)
        self.fov_max_label.setText(f"/ {max_fov}")

        # Detect available channels from first FOV
        self.setup_channel_checkboxes(project_data)

        # Enable visualization button
        self.visualize_button.setEnabled(True)

        # Enable the selection group
        self.selection_group.setEnabled(True)

    def show_project_details(self, project_data: dict):
        """Display a summary of the loaded project data."""
        details = []

        # Project path
        project_path = project_data.get("project_path", "Unknown")
        details.append(f"📁 Project Path: {project_path}")

        # Basic info
        n_fov = project_data.get("n_fov", 0)
        nd2_file = project_data.get("nd2_file", "Unknown")
        details.append(f"🔬 Source ND2: {nd2_file}")
        details.append(f"📊 FOVs: {n_fov}")

        # Processing status
        has_project_file = project_data.get("has_project_file", False)
        processing_status = project_data.get("processing_status", "unknown")
        status_icon = (
            "✅"
            if processing_status == "completed"
            else "⚠️"
            if processing_status == "partial"
            else "🔄"
        )
        details.append(f"{status_icon} Status: {processing_status.title()}")
        details.append(f"📋 Has Project File: {'Yes' if has_project_file else 'No'}")

        # Available data types (from first FOV)
        if project_data.get("fov_data"):
            first_fov_data = list(project_data["fov_data"].values())[0]
            data_types = []

            # Count channels
            fl_channels = set()
            pc_channels = set()
            seg_types = set()

            for data_type in first_fov_data.keys():
                if data_type == "traces":
                    data_types.append("📈 Traces (CSV)")
                elif data_type.startswith("fl_ch_") or data_type.startswith(
                    "fl_corrected_ch_"
                ):
                    parts = data_type.split("_ch_")
                    if len(parts) == 2:
                        try:
                            channel = int(parts[1])
                            fl_channels.add(channel)
                        except ValueError:
                            pass
                elif data_type.startswith("pc_ch_"):
                    parts = data_type.split("_ch_")
                    if len(parts) == 2:
                        try:
                            channel = int(parts[1])
                            pc_channels.add(channel)
                        except ValueError:
                            pass
                elif data_type.startswith("seg"):
                    seg_types.add(data_type)

            # Summarize channels
            if pc_channels:
                data_types.append(f"🔍 Phase Contrast: {len(pc_channels)} channel(s)")
            if fl_channels:
                data_types.append(
                    f"💚 Fluorescence: {len(fl_channels)} channel(s) [{', '.join(map(str, sorted(fl_channels)))}]"
                )
            if seg_types:
                data_types.append(f"🎯 Segmentation: {len(seg_types)} type(s)")

            details.append("")
            details.append("📋 Available Data:")
            details.extend([f"   • {dt}" for dt in data_types])

        # Display in text widget
        details_text = "\n".join(details)
        self.project_details_text.setPlainText(details_text)
        self.project_details_text.setVisible(True)

    def setup_channel_checkboxes(self, project_data: dict):
        """Setup channel selection checkboxes based on available data."""
        # Clear existing fluorescence checkboxes
        for checkbox in self.fl_checkboxes:
            checkbox.deleteLater()
        self.fl_checkboxes.clear()

        # Get first FOV to detect available channels
        first_fov_data = list(project_data["fov_data"].values())[0]

        # Find fluorescence channels
        fl_channels = set()
        has_pc = False
        has_seg = False

        for data_type in first_fov_data.keys():
            if data_type.startswith("fl_ch_") or data_type.startswith(
                "fl_corrected_ch_"
            ):
                # Extract channel number
                parts = data_type.split("_ch_")
                if len(parts) == 2:
                    try:
                        channel = int(parts[1])
                        fl_channels.add(channel)
                    except ValueError:
                        pass
            elif data_type.startswith("pc_ch_"):
                has_pc = True
            elif data_type.startswith("seg"):
                has_seg = True

        # Debug logging
        logger.info(
            f"Channel detection - PC: {has_pc}, Seg: {has_seg}, FL: {fl_channels}"
        )

        # Enable/disable checkboxes based on available data
        self.pc_checkbox.setEnabled(has_pc)
        self.seg_checkbox.setEnabled(has_seg)

        # Create fluorescence channel checkboxes
        for channel in sorted(fl_channels):
            checkbox = QCheckBox(f"Fluorescence Channel {channel}")
            checkbox.setChecked(
                channel == min(fl_channels)
            )  # Check first channel by default
            checkbox.setEnabled(True)
            self.fl_checkboxes.append(checkbox)
            self.fl_layout.addWidget(checkbox)

        self.available_channels = sorted(fl_channels)

    def on_fov_changed(self):
        """Handle FOV spinbox value change."""
        # Reset visualization state when FOV changes
        self.visualization_started = False
        self.visualize_button.setText("Start Visualization")
        self.visualize_button.setEnabled(True)

    # Progress bar control methods (used by main window)
    def start_progress(self, message: str) -> None:
        """Start progress indication with message."""
        self.progress_bar.setRange(0, 0)  # Indeterminate/busy
        self.progress_bar.setFormat(message)
        self.progress_bar.setVisible(True)

    def update_progress_message(self, message: str) -> None:
        """Update progress message."""
        self.progress_bar.setFormat(message)

    def finish_progress(self) -> None:
        """Hide progress bar when done."""
        self.progress_bar.setVisible(False)

    def get_selected_channels(self):
        """Get list of selected channels for visualization."""
        selected_channels = []

        # Add phase contrast if selected and available
        if self.pc_checkbox.isChecked() and self.pc_checkbox.isEnabled():
            selected_channels.append("pc")

        # Add selected fluorescence channels
        for i, checkbox in enumerate(self.fl_checkboxes):
            if checkbox.isChecked():
                channel_num = self.available_channels[i]
                selected_channels.append(f"fl_{channel_num}")

        # Add segmentation if selected and available
        if self.seg_checkbox.isChecked() and self.seg_checkbox.isEnabled():
            selected_channels.append("seg")

        return selected_channels

    def on_visualize_clicked(self):
        """Handle visualization button click."""
        if self.current_project is None:
            return

        if not self.visualization_started:
            # Get current selections
            fov_idx = self.fov_spinbox.value()
            selected_channels = self.get_selected_channels()

            if not selected_channels:
                QMessageBox.warning(
                    self,
                    "No Channels Selected",
                    "Please select at least one channel to visualize.",
                )
                return

            # Check if selected FOV exists
            if fov_idx not in self.current_project["fov_data"]:
                QMessageBox.warning(
                    self,
                    "Invalid FOV",
                    f"FOV {fov_idx} does not exist in the loaded project.",
                )
                return

            # Start visualization
            self.visualization_requested.emit(fov_idx, selected_channels)
            self.visualization_started = True
            self.visualize_button.setText("Loading...")
            self.visualize_button.setEnabled(False)

        else:
            # Reset visualization state
            self.visualization_started = False
            self.visualize_button.setText("Start Visualization")
            self.visualize_button.setEnabled(True)
