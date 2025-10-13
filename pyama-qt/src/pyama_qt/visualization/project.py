"""Project loader panel for the visualization application."""

# =============================================================================
# IMPORTS
# =============================================================================

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
from pyama_qt.constants import DEFAULT_DIR

logger = logging.getLogger(__name__)


# =============================================================================
# CHANNEL LIST MODEL
# =============================================================================

class ChannelListModel(QAbstractListModel):
    """Model for displaying available channels in a list view."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self) -> None:
        super().__init__()
        self._channels: list[tuple[str, str]] = []  # (display_name, internal_name)

    # ------------------------------------------------------------------------
    # QAbstractListModel INTERFACE
    # ------------------------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of channels."""
        return len(self._channels)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Return data for the given index and role."""
        if not index.isValid() or not (0 <= index.row() < len(self._channels)):
            return None
        display_name, internal_name = self._channels[index.row()]
        if role == Qt.DisplayRole:
            return display_name
        if role == Qt.UserRole:
            return internal_name
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return item flags for the given index."""
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    # ------------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------------
    def set_channels(self, channels: list[str]) -> None:
        """Update the list of channels."""
        self.beginResetModel()
        self._channels = [(name, name) for name in sorted(channels)]
        self.endResetModel()

    def internal_name(self, row: int) -> str:
        """Get the internal name for a given row."""
        return self._channels[row][1] if 0 <= row < len(self._channels) else ""


# =============================================================================
# MAIN PROJECT PANEL
# =============================================================================

class ProjectPanel(QWidget):
    """Panel for loading and displaying FOV data from folders."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    projectLoaded = Signal(dict)           # Project data loaded
    visualizationRequested = Signal(int, list)  # FOV index and channels
    statusMessage = Signal(str)            # Status messages
    errorMessage = Signal(str)             # Error messages
    loadingStateChanged = Signal(bool)     # Loading state changes

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._build_ui()
        self._connect_signals()
        self._project_data: dict | None = None

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout."""
        layout = QVBoxLayout(self)
        
        # Data loading section
        load_group = self._build_load_section()
        layout.addWidget(load_group, 1)
        
        # Visualization settings section
        selection_group = self._build_selection_section()
        layout.addWidget(selection_group, 1)

    def _build_load_section(self) -> QGroupBox:
        """Build the data loading section."""
        group = QGroupBox("Load Data Folder")
        load_layout = QVBoxLayout(group)
        
        self.load_button = QPushButton("Load Folder")
        load_layout.addWidget(self.load_button)
        
        self.project_details_text = QTextEdit()
        self.project_details_text.setReadOnly(True)
        load_layout.addWidget(self.project_details_text)
        
        return group

    def _build_selection_section(self) -> QGroupBox:
        """Build the visualization settings section."""
        group = QGroupBox("Visualization Settings")
        selection_layout = QVBoxLayout(group)
        
        # FOV selection row
        fov_row = QHBoxLayout()
        self.fov_spinbox = QSpinBox()
        self.fov_max_label = QLabel("/ 0")
        fov_row.addWidget(QLabel("FOV:"))
        fov_row.addStretch()
        fov_row.addWidget(self.fov_spinbox)
        fov_row.addWidget(self.fov_max_label)
        selection_layout.addLayout(fov_row)
        
        # Channel selection list
        self.channels_list = QListView()
        self.channels_list.setSelectionMode(QListView.SelectionMode.MultiSelection)
        self.channels_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.channels_list.setVisible(False)
        selection_layout.addWidget(self.channels_list)
        self._channel_model = ChannelListModel()
        self.channels_list.setModel(self._channel_model)
        
        # Visualization button
        self.visualize_button = QPushButton("Start Visualization")
        self.visualize_button.setVisible(False)
        selection_layout.addWidget(self.visualize_button)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        selection_layout.addWidget(self.progress_bar)
        
        return group

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers."""
        self.load_button.clicked.connect(self._on_load_folder_clicked)
        self.visualize_button.clicked.connect(self._on_visualize_clicked)


    # ------------------------------------------------------------------------
    # PUBLIC API AND SLOTS
    # ------------------------------------------------------------------------
    def set_loading(self, is_loading: bool):
        """Set the loading state and update UI accordingly."""
        self.loadingStateChanged.emit(is_loading)
        if is_loading:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            self.visualize_button.setText("Loading...")
        else:
            self.progress_bar.setVisible(False)
            self.visualize_button.setText("Start Visualization")

    def on_processing_status_changed(self, is_processing: bool):
        """Handle processing status changes from other tabs."""
        self.visualize_button.setEnabled(not is_processing)
        if is_processing:
            self.visualize_button.setText("Processing Active")
        else:
            self.visualize_button.setText("Start Visualization")

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    def _on_load_folder_clicked(self):
        """Handle folder load button click."""
        logger.debug("UI Click: Load project folder button")
        directory = QFileDialog.getExistingDirectory(
            self, "Select Data Folder", str(DEFAULT_DIR)
        )
        if directory:
            logger.debug("UI Action: Loading project from - %s", directory)
            self._load_project(Path(directory))

    def _on_visualize_clicked(self):
        """Handle visualization button click."""
        logger.debug("UI Click: Start visualization button")
        selected_channels = [
            self._channel_model.internal_name(idx.row()) 
            for idx in self.channels_list.selectionModel().selectedIndexes()
        ]
        if not selected_channels:
            logger.debug("UI Action: No channels selected, showing error")
            self.errorMessage.emit("No channels selected for visualization.")
            return
        logger.debug("UI Event: Emitting visualizationRequested - FOV=%d, channels=%s", 
                    self.fov_spinbox.value(), selected_channels)
        self.visualizationRequested.emit(self.fov_spinbox.value(), selected_channels)

    # ------------------------------------------------------------------------
    # PROJECT LOADING
    # ------------------------------------------------------------------------
    def _load_project(self, project_path: Path):
        """Load project data from the given path."""
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

    # ------------------------------------------------------------------------
    # UI UPDATES
    # ------------------------------------------------------------------------
    def _update_ui_with_project_data(self, project_data: dict):
        """Update UI elements with loaded project data."""
        self._set_project_details_text(project_data)
        
        # Update channel list
        channels = self._extract_available_channels(project_data)
        self._channel_model.set_channels(channels)
        self.channels_list.setVisible(bool(channels))
        self.visualize_button.setVisible(bool(channels))
        
        # Update FOV range
        fov_keys = list(project_data.get("fov_data", {}).keys())
        min_fov, max_fov = (min(fov_keys), max(fov_keys)) if fov_keys else (0, 0)
        self.fov_spinbox.setRange(min_fov, max_fov)
        self.fov_max_label.setText(f"/ {max_fov}")
        self.channels_list.selectionModel().clear()

    def _set_project_details_text(self, project_data: dict):
        """Set the project details text in the UI."""
        details = [
            f"Project Path: {project_data.get('project_path', 'Unknown')}",
            f"FOVs: {project_data.get('n_fov', 0)}"
        ]
        
        if time_units := project_data.get("time_units"):
            details.append(f"Time Units: {time_units}")
            
        if project_data.get("fov_data"):
            first_fov = next(iter(project_data["fov_data"].values()))
            details.append("Available Data:")
            details.extend([f"   • {dt}" for dt in first_fov.keys()])
            
        self.project_details_text.setPlainText("\n".join(details))

    # ------------------------------------------------------------------------
    # UTILITY METHODS
    # ------------------------------------------------------------------------
    @staticmethod
    def _extract_available_channels(project_data: dict) -> list[str]:
        """Extract available channels from project data."""
        if not project_data.get("fov_data"):
            return []
        first_fov = next(iter(project_data["fov_data"].values()))
        channels = [
            k for k in first_fov.keys() 
            if not k.startswith("traces") and not k.startswith("seg")
        ]
        return sorted(channels)

    @staticmethod
    def _format_project_status(project_data: dict) -> str:
        """Format project status for display."""
        status = project_data.get("processing_status", "unknown")
        n_fov = project_data.get("n_fov", 0)
        msg = f"Project loaded: {n_fov} FOVs, Status: {status.title()}"
        return msg + " ⚠" if status != "completed" else msg

    @staticmethod
    def _format_project_error(project_path: Path, exc: Exception) -> str:
        """Format project error messages for user display."""
        msg = str(exc)
        if "No FOV directories found" in msg:
            return f"No data found in {project_path}. Ensure it contains FOV subdirectories."
        return msg