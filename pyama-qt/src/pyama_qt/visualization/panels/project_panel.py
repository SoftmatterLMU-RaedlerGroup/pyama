"""Project loader panel for the visualization application.

Simplified behavior:
- Use QListView with QAbstractListModel for multi-selection channel selection with proper model-view architecture
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
    QMessageBox,
    QProgressBar,
    QTextEdit,
    QListView,
    QAbstractItemView,
)

from pyama_qt.config import DEFAULT_DIR
from PySide6.QtCore import Qt, Signal, QModelIndex, QAbstractListModel
from pathlib import Path
import logging
from typing import Any

from pyama_qt.visualization.models import ProjectModel
from pyama_qt.ui import ModelBoundPanel

logger = logging.getLogger(__name__)


class ChannelListModel(QAbstractListModel):
    """Model for displaying available channels in a list view."""

    def __init__(self) -> None:
        super().__init__()
        self._channels: list[tuple[str, str]] = []  # (display_name, internal_name)

    def rowCount(self, parent: QModelIndex = None) -> int:  # noqa:N802
        """Return number of available channels."""
        if parent is not None and parent.isValid():
            return 0
        return len(self._channels)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa:N802
        """Return data for the given role at the given index."""
        if not index.isValid() or not (0 <= index.row() < len(self._channels)):
            return None

        display_name, internal_name = self._channels[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return display_name
        elif role == Qt.ItemDataRole.UserRole:
            return internal_name
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # noqa:N802
        """Return flags for the given index."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def set_channels(self, channels: list[str]) -> None:
        """Update the model with new available channels."""
        self.beginResetModel()
        self._channels.clear()

        # Use raw channel names directly without processing
        for channel_name in sorted(channels):
            self._channels.append((channel_name, channel_name))

        self.endResetModel()

    def get_channel_name(self, index: int) -> str:
        """Get the internal channel name for the given index."""
        if 0 <= index < len(self._channels):
            return self._channels[index][1]
        return ""


class ProjectPanel(ModelBoundPanel):
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

        # Channel selection section (hidden until project loaded)
        # Channel selection section - label always visible
        channels_label = QLabel("Channels to load:")
        channels_label.setStyleSheet("font-weight: bold;")
        selection_layout.addWidget(channels_label)

        # Channel selection list view with model
        self.channels_list = QListView()
        # Configure for multi-selection
        self.channels_list.setSelectionMode(QListView.SelectionMode.MultiSelection)
        self.channels_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.channels_list.setVisible(False)
        selection_layout.addWidget(self.channels_list)

        # Channel list model
        self._channel_model = ChannelListModel()
        self.channels_list.setModel(self._channel_model)

        # Track whether channel list has been initialized
        self._channel_list_initialized = False

        # Visualization button
        self.visualize_button = QPushButton("Start Visualization")
        self.visualize_button.clicked.connect(self._on_visualize_clicked)
        self.visualize_button.setVisible(False)
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

    def set_models(self, project_model: ProjectModel) -> None:
        self._model = project_model
        project_model.projectDataChanged.connect(self._on_project_data_changed)
        project_model.availableChannelsChanged.connect(self._setup_channel_list)
        project_model.statusMessageChanged.connect(self._on_status_changed)
        project_model.isLoadingChanged.connect(self._on_loading_changed)

    def _on_project_data_changed(self, project_data: dict) -> None:
        if project_data:
            self._show_project_details(project_data)
            max_fov = max(project_data.get("fov_data", {0: None}).keys())
            self.fov_spinbox.setMaximum(max_fov)
            self.fov_max_label.setText(f"/ {max_fov}")

    def _on_status_changed(self, message: str) -> None:
        if self.progress_bar.isVisible():
            self.progress_bar.setFormat(message)

    def _on_loading_changed(self, is_loading: bool) -> None:
        if is_loading:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setVisible(False)
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
        if not self._model or not self._model.project_data():
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
        project_data = self._model.project_data() or {}
        if fov_idx not in project_data.get("fov_data", {}):
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

    def _setup_channel_list(self, available_channels: list[str]) -> None:
        """Setup channel list view based on available channels.

        This method only runs once when project is first loaded to avoid overwriting user selections.
        """
        # Only run once when project is first loaded
        if self._channel_list_initialized:
            return

        self._channel_list_initialized = True

        # Show channels list view if there are any available channels
        self.channels_list.setVisible(len(available_channels) > 0)
        self.visualize_button.setVisible(True)

        # Update the model with available channels
        self._channel_model.set_channels(available_channels)

        # Select all channels by default
        selection_model = self.channels_list.selectionModel()
        if selection_model:
            selection_model.clear()
            # Select all items using the view's selectAll() method
            self.channels_list.selectAll()

    def _get_selected_channels(self) -> list[str]:
        """Get list of selected channels from the list view."""
        selected_channels = []

        selection_model = self.channels_list.selectionModel()
        if selection_model:
            selected_indexes = selection_model.selectedIndexes()
            for index in selected_indexes:
                if index.isValid():
                    channel_name = self._channel_model.data(
                        index, Qt.ItemDataRole.UserRole
                    )
                    if channel_name:
                        selected_channels.append(channel_name)

        return selected_channels
