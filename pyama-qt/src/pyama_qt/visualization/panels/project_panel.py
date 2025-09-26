"""Project loader panel for the visualization application.

Simplified behavior:
- Avoid explicit enable/disable toggles for widgets; widgets are left in their
  default interactive state. Controllers or callers should manage availability
  if needed.
- Removed checks that relied on widget enabled state when collecting selections.
"""

from __future__ import annotations

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

from pyama_qt.config import DEFAULT_DIR
from PySide6.QtCore import Signal
from pathlib import Path
import logging

from pyama_qt.visualization.state import VisualizationState
from pyama_qt.ui import BasePanel

logger = logging.getLogger(__name__)


class ProjectPanel(BasePanel[VisualizationState]):
    """Panel for loading and displaying FOV data from folders.

    This panel exposes:
    - `project_load_requested` (Path) signal when the user chooses a folder.
    - `visualization_requested` (int, list) signal with FOV index and selected channels.
    """

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
        self.pc_checkbox.setChecked(False)
        selection_layout.addWidget(self.pc_checkbox)

        # Fluorescence channels (dynamic)
        self.fl_checkboxes = []
        self.fl_layout = QVBoxLayout()
        selection_layout.addLayout(self.fl_layout)

        # Track whether checkboxes have been initialized
        self._checkboxes_initialized = False

        # Segmentation channel
        self.seg_checkbox = QCheckBox("Segmentation")
        self.seg_checkbox.setChecked(False)
        selection_layout.addWidget(self.seg_checkbox)

        # Visualization button
        self.visualize_button = QPushButton("Start Visualization")
        self.visualize_button.clicked.connect(self._on_visualize_clicked)
        selection_layout.addWidget(self.visualize_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        selection_layout.addWidget(self.progress_bar)

        layout.addWidget(selection_group, 1)

        # Keep reference to selection group in case external code wants to show/hide it
        self.selection_group = selection_group

    def bind(self) -> None:
        # No additional bindings needed for this panel
        pass

    def set_state(self, state: VisualizationState) -> None:
        super().set_state(state)

        if state.project_data:
            self._update_project_ui(state)

        # Update progress bar and button state
        if state.is_loading:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.progress_bar.setFormat(state.status_message)
            # Log worker progress
            logger.info("Visualization progress: %s", state.status_message)
        else:
            self.progress_bar.setVisible(False)
            # Reset visualization button text when not loading
            if self.visualize_button.text() == "Loading...":
                self.visualize_button.setText("Start Visualization")

    # Event handlers -------------------------------------------------------
    def _on_load_folder_clicked(self) -> None:
        """Handle load folder button click."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Data Folder",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            # Reset checkbox initialization flag for new project
            self._checkboxes_initialized = False
            self.project_load_requested.emit(Path(directory))

    def _on_fov_changed(self) -> None:
        """Handle FOV spinbox value change."""
        # Reset visualization button text to indicate ready state
        self.visualize_button.setText("Start Visualization")

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

        # Update button text to indicate work in progress; do not toggle enabled state here.
        self.visualize_button.setText("Loading...")

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
        self.fov_max_label.setText(f"/ {max_fov}")

        # Setup channel checkboxes
        self._setup_channel_checkboxes(state.available_channels)

        # Optionally let external code decide whether selection_group should be visible
        # or interactive. Keep UI predictable and do not toggle enable state here.
        self.selection_group.setVisible(True)

    def _show_project_details(self, project_data: dict) -> None:
        """Display a summary of the loaded project data."""
        details = []

        # Project path
        project_path = project_data.get("project_path", "Unknown")
        details.append(f"Project Path: {project_path}")

        # Basic info
        n_fov = project_data.get("n_fov", 0)
        details.append(f"FOVs: {n_fov}")

        # Channels
        channels = project_data.get("channels", {})
        if channels:
            details.append("Channels:")
            for channel_type, indices in channels.items():
                details.append(f"   • {channel_type}: {indices}")

        # Time units
        time_units = project_data.get("time_units")
        if time_units:
            details.append(f"Time Units: {time_units}")

        # Available data types
        if project_data.get("fov_data"):
            first_fov = next(iter(project_data["fov_data"].values()))
            data_types = list(first_fov.keys())
            details.append("Available Data:")
            details.extend([f"   • {dt}" for dt in data_types])

        # Display in text widget
        details_text = "\n".join(details)
        self.project_details_text.setPlainText(details_text)

    def _setup_channel_checkboxes(self, available_channels: list[str]) -> None:
        """Setup channel checkboxes based on available channels.

        This method only runs once when project is first loaded to avoid overwriting user selections.
        """
        # Only run once when project is first loaded
        if self._checkboxes_initialized:
            return

        self._checkboxes_initialized = True

        current_fl_states = {}
        for i, checkbox in enumerate(self.fl_checkboxes):
            current_fl_states[f"fl_{i + 1}"] = checkbox.isChecked()

        # Clear existing fluorescence checkboxes
        for checkbox in self.fl_checkboxes:
            checkbox.deleteLater()
        self.fl_checkboxes.clear()

        # DO NOT modify pc_checkbox or seg_checkbox states - leave them as user set them

        # Create fluorescence channel checkboxes - preserve previous selections
        fl_channels = [ch for ch in available_channels if ch.startswith("fl_")]
        for channel in sorted(fl_channels):
            checkbox = QCheckBox(f"Fluorescence {channel.split('_')[1]}")
            # Preserve previous state if it existed, otherwise default to False for new channels
            previous_state = current_fl_states.get(channel, False)
            checkbox.setChecked(previous_state)
            self.fl_checkboxes.append(checkbox)
            self.fl_layout.addWidget(checkbox)

    def _get_selected_channels(self) -> list[str]:
        """Get list of selected channels for visualization.

        Note: we no longer rely on widget enabled state to decide whether a
        channel is available; availability is handled by setup logic above.
        """
        selected_channels = []

        # Add phase contrast if selected
        if self.pc_checkbox.isChecked():
            selected_channels.append("pc")

        # Add selected fluorescence channels
        for i, checkbox in enumerate(self.fl_checkboxes):
            if checkbox.isChecked():
                selected_channels.append(f"fl_{i + 1}")

        # Add segmentation if selected
        if self.seg_checkbox.isChecked():
            selected_channels.append("seg")

        return selected_channels
