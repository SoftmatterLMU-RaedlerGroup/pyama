"""Project loader panel for the visualization application.

Simplified behavior:
- Use QListView with QAbstractListModel for multi-selection channel selection with proper model-view architecture
- Avoid explicit enable/disable toggles for widgets; widgets are left in their
  default interactive state. Controllers or callers should manage availability
  if needed.
- Removed checks that relied on widget enabled state when collecting selections.
"""

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QFileDialog,
    QSpinBox,
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

from ..base import BasePanel

logger = logging.getLogger(__name__)


class ChannelListModel(QAbstractListModel):
    """Model for displaying available channels in a list view."""

    def __init__(self) -> None:
        super().__init__()
        self._channels: list[tuple[str, str]] = []  # (display_name, internal_name)

    def rowCount(self, parent: QModelIndex) -> int:  # noqa:N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._channels)

    def data(  # noqa:N802
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._channels)):
            return None

        display_name, internal_name = self._channels[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return display_name
        if role == Qt.ItemDataRole.UserRole:
            return internal_name
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # noqa:N802
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def set_channels(self, channels: list[str]) -> None:
        self.beginResetModel()
        self._channels = [(name, name) for name in sorted(channels)]
        self.endResetModel()

    def clear(self) -> None:
        self.set_channels([])

    def internal_name(self, row: int) -> str:
        if 0 <= row < len(self._channels):
            return self._channels[row][1]
        return ""


class ProjectPanel(BasePanel):
    """Panel for loading and displaying FOV data from folders."""

    project_load_requested = Signal(Path)
    visualization_requested = Signal(int, list)

    def build(self) -> None:
        layout = QVBoxLayout(self)

        load_group = QGroupBox("Load Data Folder")
        load_layout = QVBoxLayout(load_group)

        self.load_button = QPushButton("Load Folder")
        self.load_button.setToolTip("Load a folder containing FOV subdirectories")
        load_layout.addWidget(self.load_button)

        self.project_details_text = QTextEdit()
        self.project_details_text.setReadOnly(True)
        load_layout.addWidget(self.project_details_text)

        layout.addWidget(load_group, 1)

        selection_group = QGroupBox("Visualization Settings")
        selection_layout = QVBoxLayout(selection_group)

        fov_row = QHBoxLayout()
        self.fov_spinbox = QSpinBox()
        self.fov_spinbox.setMinimum(0)
        self.fov_spinbox.setMaximum(0)
        self.fov_spinbox.valueChanged.connect(self._on_fov_changed)

        self.fov_max_label = QLabel("/ 0")
        self.fov_max_label.setStyleSheet("color: gray;")

        fov_row.addWidget(QLabel("FOV:"))
        fov_row.addStretch()
        fov_row.addWidget(self.fov_spinbox)
        fov_row.addWidget(self.fov_max_label)
        selection_layout.addLayout(fov_row)

        channels_label = QLabel("Channels to load:")
        channels_label.setStyleSheet("font-weight: bold;")
        selection_layout.addWidget(channels_label)

        self.channels_list = QListView()
        self.channels_list.setSelectionMode(QListView.SelectionMode.MultiSelection)
        self.channels_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.channels_list.setVisible(False)
        selection_layout.addWidget(self.channels_list)

        self._channel_model = ChannelListModel()
        self.channels_list.setModel(self._channel_model)

        self.visualize_button = QPushButton("Start Visualization")
        selection_layout.addWidget(self.visualize_button)
        self.visualize_button.setVisible(False)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        selection_layout.addWidget(self.progress_bar)

        layout.addWidget(selection_group, 1)

    def bind(self) -> None:
        self.load_button.clicked.connect(self._on_load_folder_clicked)
        self.visualize_button.clicked.connect(self._on_visualize_clicked)

    # ------------------------------------------------------------------
    # View → Controller helpers
    # ------------------------------------------------------------------
    def _on_load_folder_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Data Folder",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self.project_load_requested.emit(Path(directory))

    def _on_fov_changed(self) -> None:
        if not self.visualize_button.isVisible():
            return
        self.visualize_button.setText("Start Visualization")

    def _on_visualize_clicked(self) -> None:
        selected_channels = self._selected_channels()
        if not selected_channels:
            logger.warning("No channels selected for visualization")
            return

        fov_idx = self.fov_spinbox.value()
        self.visualization_requested.emit(fov_idx, selected_channels)
        self.visualize_button.setText("Loading...")

    # ------------------------------------------------------------------
    # Controller-facing API
    # ------------------------------------------------------------------
    def set_project_details(self, project_data: dict) -> None:
        details = []
        project_path = project_data.get("project_path", "Unknown")
        details.append(f"Project Path: {project_path}")

        n_fov = project_data.get("n_fov", 0)
        details.append(f"FOVs: {n_fov}")

        channels = project_data.get("channels", {})
        if channels:
            details.append("Channels:")
            for channel_type, indices in channels.items():
                details.append(f"   • {channel_type}: {indices}")

        time_units = project_data.get("time_units")
        if time_units:
            details.append(f"Time Units: {time_units}")

        if project_data.get("fov_data"):
            first_fov = next(iter(project_data["fov_data"].values()))
            data_types = list(first_fov.keys())
            details.append("Available Data:")
            details.extend([f"   • {dt}" for dt in data_types])

        self.project_details_text.setPlainText("\n".join(details))

        fov_keys = list(project_data.get("fov_data", {}).keys())
        if fov_keys:
            min_fov = min(fov_keys)
            max_fov = max(fov_keys)
        else:
            min_fov = 0
            max_fov = 0
        self.set_fov_range(min_fov, max_fov)

    def set_fov_range(self, minimum: int, maximum: int) -> None:
        self.fov_spinbox.blockSignals(True)
        self.fov_spinbox.setMinimum(minimum)
        self.fov_spinbox.setMaximum(maximum)
        if minimum <= self.fov_spinbox.value() <= maximum:
            pass
        else:
            self.fov_spinbox.setValue(minimum)
        self.fov_spinbox.blockSignals(False)
        self.fov_max_label.setText(f"/ {maximum}")

    def set_available_channels(self, channels: list[str]) -> None:
        self._channel_model.set_channels(channels)
        selection_model = self.channels_list.selectionModel()
        if selection_model:
            selection_model.clear()
        has_channels = bool(channels)
        self.channels_list.setVisible(has_channels)
        self.visualize_button.setVisible(has_channels)
        self.visualize_button.setText("Start Visualization")

    def reset_channel_selection(self) -> None:
        selection_model = self.channels_list.selectionModel()
        if selection_model:
            selection_model.clear()

    def set_status_message(self, message: str) -> None:
        if not message:
            self.progress_bar.setFormat("")
            return
        self.progress_bar.setFormat(message)

    def set_loading(self, is_loading: bool) -> None:
        if is_loading:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setVisible(False)
            if self.visualize_button.text() == "Loading...":
                self.visualize_button.setText("Start Visualization")

    def set_visualize_button_text(self, text: str) -> None:
        self.visualize_button.setText(text)

    def set_visualize_enabled(self, enabled: bool) -> None:
        """Enable or disable the visualize button."""
        self.visualize_button.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _selected_channels(self) -> list[str]:
        channels = []
        selection = self.channels_list.selectionModel()
        if not selection:
            return channels
        for index in selection.selectedIndexes():
            channels.append(self._channel_model.internal_name(index.row()))
        return channels

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
            logger.warning("No channels selected for visualization")
            return

        # Check if selected FOV exists
        project_data = self._model.project_data() or {}
        if fov_idx not in project_data.get("fov_data", {}):
            logger.warning(f"FOV {fov_idx} does not exist in the loaded project.")
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

        # Don't pre-select any channels - let user choose
        selection_model = self.channels_list.selectionModel()
        if selection_model:
            selection_model.clear()

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
