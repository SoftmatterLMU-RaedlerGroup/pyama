"""Project loader panel for the visualization application."""

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, QModelIndex, QAbstractListModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pyama_core.io.results_yaml import discover_processing_results
from pyama_qt.config import DEFAULT_DIR


logger = logging.getLogger(__name__)


class ChannelListModel(QAbstractListModel):
    """Model for displaying available channels in a list view."""

    def __init__(self) -> None:
        super().__init__()
        self._channels: list[tuple[str, str]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._channels)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._channels)):
            return None
        display_name, internal_name = self._channels[index.row()]
        if role == Qt.DisplayRole:
            return display_name
        if role == Qt.UserRole:
            return internal_name
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def set_channels(self, channels: list[str]) -> None:
        self.beginResetModel()
        self._channels = [(name, name) for name in sorted(channels)]
        self.endResetModel()

    def internal_name(self, row: int) -> str:
        return self._channels[row][1] if 0 <= row < len(self._channels) else ""


class ProjectPanel(QWidget):
    """Panel for loading and displaying FOV data from folders."""

    # Signals for other components
    projectLoaded = Signal(dict)
    visualizationRequested = Signal(int, list)
    statusMessage = Signal(str)
    errorMessage = Signal(str)
    loadingStateChanged = Signal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.build()
        self.bind()
        self._project_data: dict | None = None

    def build(self) -> None:
        layout = QVBoxLayout(self)
        load_group = QGroupBox("Load Data Folder")
        load_layout = QVBoxLayout(load_group)
        self.load_button = QPushButton("Load Folder")
        load_layout.addWidget(self.load_button)
        self.project_details_text = QTextEdit()
        self.project_details_text.setReadOnly(True)
        load_layout.addWidget(self.project_details_text)
        layout.addWidget(load_group, 1)

        selection_group = QGroupBox("Visualization Settings")
        selection_layout = QVBoxLayout(selection_group)
        fov_row = QHBoxLayout()
        self.fov_spinbox = QSpinBox()
        self.fov_max_label = QLabel("/ 0")
        fov_row.addWidget(QLabel("FOV:"))
        fov_row.addStretch()
        fov_row.addWidget(self.fov_spinbox)
        fov_row.addWidget(self.fov_max_label)
        selection_layout.addLayout(fov_row)
        self.channels_list = QListView()
        self.channels_list.setSelectionMode(QListView.SelectionMode.MultiSelection)
        self.channels_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.channels_list.setVisible(False)
        selection_layout.addWidget(self.channels_list)
        self._channel_model = ChannelListModel()
        self.channels_list.setModel(self._channel_model)
        self.visualize_button = QPushButton("Start Visualization")
        self.visualize_button.setVisible(False)
        selection_layout.addWidget(self.visualize_button)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        selection_layout.addWidget(self.progress_bar)
        layout.addWidget(selection_group, 1)

    def bind(self) -> None:
        self.load_button.clicked.connect(self._on_load_folder_clicked)
        self.visualize_button.clicked.connect(self._on_visualize_clicked)

    # --- Public API & Slots ---
    def set_loading(self, is_loading: bool):
        self.loadingStateChanged.emit(is_loading)
        if is_loading:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.visualize_button.setText("Loading...")
        else:
            self.progress_bar.setVisible(False)
            self.visualize_button.setText("Start Visualization")

    def on_processing_status_changed(self, is_processing: bool):
        self.visualize_button.setEnabled(not is_processing)
        if is_processing:
            self.visualize_button.setText("Processing Active")
        else:
            self.visualize_button.setText("Start Visualization")

    # --- Internal Logic ---
    def _on_load_folder_clicked(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Data Folder", str(DEFAULT_DIR))
        if directory:
            self._load_project(Path(directory))

    def _load_project(self, project_path: Path):
        logger.info("Loading project from %s", project_path)
        self.set_loading(True)
        self.statusMessage.emit(f"Loading project: {project_path.name}")
        try:
            project_results = discover_processing_results(project_path)
            project_data = project_results.to_dict()
            self._project_data = project_data
            self._update_ui_with_project_data(project_data)
            self.projectLoaded.emit(project_data)
            self.statusMessage.emit(self._format_project_status(project_data))
        except Exception as exc:
            message = self._format_project_error(project_path, exc)
            logger.exception("Failed to load project")
            self.errorMessage.emit(message)
            self.statusMessage.emit(message)
        finally:
            self.set_loading(False)

    def _update_ui_with_project_data(self, project_data: dict):
        self._set_project_details_text(project_data)
        channels = self._extract_available_channels(project_data)
        self._channel_model.set_channels(channels)
        self.channels_list.setVisible(bool(channels))
        self.visualize_button.setVisible(bool(channels))
        fov_keys = list(project_data.get("fov_data", {}).keys())
        min_fov, max_fov = (min(fov_keys), max(fov_keys)) if fov_keys else (0, 0)
        self.fov_spinbox.setRange(min_fov, max_fov)
        self.fov_max_label.setText(f"/ {max_fov}")
        self.channels_list.selectionModel().clear()

    def _on_visualize_clicked(self):
        selected_channels = [self._channel_model.internal_name(idx.row()) for idx in self.channels_list.selectionModel().selectedIndexes()]
        if not selected_channels:
            self.errorMessage.emit("No channels selected for visualization.")
            return
        self.visualizationRequested.emit(self.fov_spinbox.value(), selected_channels)

    def _set_project_details_text(self, project_data: dict):
        details = [f"Project Path: {project_data.get('project_path', 'Unknown')}", f"FOVs: {project_data.get('n_fov', 0)}"]
        if time_units := project_data.get("time_units"): details.append(f"Time Units: {time_units}")
        if project_data.get("fov_data"):
            first_fov = next(iter(project_data["fov_data"].values()))
            details.append("Available Data:")
            details.extend([f"   • {dt}" for dt in first_fov.keys()])
        self.project_details_text.setPlainText("\n".join(details))

    @staticmethod
    def _extract_available_channels(project_data: dict) -> list[str]:
        if not project_data.get("fov_data"): return []
        first_fov = next(iter(project_data["fov_data"].values()))
        channels = [k for k in first_fov.keys() if not k.startswith("traces") and not k.startswith("seg")]
        return sorted(channels)

    @staticmethod
    def _format_project_status(project_data: dict) -> str:
        status = project_data.get("processing_status", "unknown")
        n_fov = project_data.get("n_fov", 0)
        msg = f"Project loaded: {n_fov} FOVs, Status: {status.title()}"
        return msg + " ⚠" if status != "completed" else msg

    @staticmethod
    def _format_project_error(project_path: Path, exc: Exception) -> str:
        msg = str(exc)
        if "No FOV directories found" in msg:
            return f"No data found in {project_path}. Ensure it contains FOV subdirectories."
        return msg