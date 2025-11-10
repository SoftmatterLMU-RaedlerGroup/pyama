"""Project loader panel for the visualization application."""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pyama_core.io.results_yaml import load_processing_results_yaml
from pyama_pro.constants import DEFAULT_DIR

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN PROJECT PANEL
# =============================================================================


class LoadPanel(QWidget):
    """Panel for loading and displaying FOV data from folders.

    This panel provides an interface for loading project data from
    processing results directories and configuring visualization settings.
    It handles project discovery, FOV selection, and channel configuration
    for the visualization workflow.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    project_loaded = Signal(dict)  # Emitted when project data is loaded
    visualization_requested = Signal(
        dict, int, list
    )  # Emitted when visualization is requested (project_data, fov_index, channels)
    cleanup_requested = (
        Signal()
    )  # Emitted when cleanup is requested before visualization
    error_message = Signal(str)  # Emitted when an error occurs
    loading_state_changed = Signal(bool)  # Emitted when loading state changes
    project_loading_started = Signal()  # Emitted when project loading starts
    project_loading_finished = Signal(
        bool, str
    )  # Emitted when project loading finishes (success, message)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the load panel.

        Args:
            *args: Positional arguments passed to parent QWidget
            **kwargs: Keyword arguments passed to parent QWidget
        """
        super().__init__(*args, **kwargs)
        self._build_ui()
        self._connect_signals()
        self._project_data: dict | None = None

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout.

        Creates a vertical layout with two main sections:
        1. Data loading section for folder selection and project details
        2. Visualization settings section for FOV and channel selection
        """
        layout = QVBoxLayout(self)

        # Data loading section
        load_group = self._build_load_section()
        layout.addWidget(load_group, 1)

        # Visualization settings section
        selection_group = self._build_selection_section()
        layout.addWidget(selection_group, 1)

    def _build_load_section(self) -> QGroupBox:
        """Build the data loading section.

        Returns:
            QGroupBox containing folder selection and project details display
        """
        group = QGroupBox("Load Data Folder")
        load_layout = QVBoxLayout(group)

        self._load_button = QPushButton("Load Folder")
        load_layout.addWidget(self._load_button)

        self._project_details_text = QTextEdit()
        self._project_details_text.setReadOnly(True)
        load_layout.addWidget(self._project_details_text)

        return group

    def _build_selection_section(self) -> QGroupBox:
        """Build the visualization settings section.

        Returns:
            QGroupBox containing FOV selection, channel selection, and visualization controls
        """
        group = QGroupBox("Visualization Settings")
        selection_layout = QVBoxLayout(group)

        # FOV selection row
        fov_row = QHBoxLayout()
        self._fov_spinbox = QSpinBox()
        self._fov_max_label = QLabel("/ 0")
        fov_row.addWidget(QLabel("FOV:"))
        fov_row.addStretch()
        fov_row.addWidget(self._fov_spinbox)
        fov_row.addWidget(self._fov_max_label)
        selection_layout.addLayout(fov_row)

        # Channel selection list
        self._channels_list = QListWidget()
        self._channels_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._channels_list.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        self._channels_list.setVisible(False)
        selection_layout.addWidget(self._channels_list)

        # Visualization button
        self._visualize_button = QPushButton("Start Visualization")
        self._visualize_button.setVisible(False)
        selection_layout.addWidget(self._visualize_button)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        selection_layout.addWidget(self._progress_bar)

        return group

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers.

        Connects button clicks to their respective event handlers.
        """
        self._load_button.clicked.connect(self._on_load_folder_clicked)
        self._visualize_button.clicked.connect(self._on_visualize_clicked)

    # ------------------------------------------------------------------------
    # PUBLIC API AND SLOTS
    # ------------------------------------------------------------------------
    def set_loading(self, is_loading: bool) -> None:
        """Set the loading state and update UI accordingly.

        Args:
            is_loading: Whether the panel is in a loading state
        """
        self.loading_state_changed.emit(is_loading)
        if is_loading:
            self._progress_bar.setVisible(True)
            self._progress_bar.setRange(0, 0)  # Indeterminate progress
            self._visualize_button.setText("Loading...")
        else:
            self._progress_bar.setVisible(False)
            self._visualize_button.setText("Start Visualization")

    @Slot(bool)
    def on_processing_status_changed(self, is_processing: bool) -> None:
        """Handle processing status changes from other tabs.

        Args:
            is_processing: Whether processing is active in another tab
        """
        self._visualize_button.setEnabled(not is_processing)
        if is_processing:
            self._visualize_button.setText("Processing Active")
        else:
            self._visualize_button.setText("Start Visualization")

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot()
    def _on_load_folder_clicked(self) -> None:
        """Handle folder load button click.

        Opens a directory dialog to select a data folder and initiates
        project loading from the selected path.
        """
        logger.debug("UI Click: Load project folder button")
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Data Folder",
            str(DEFAULT_DIR),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            logger.debug("UI Action: Loading project from - %s", directory)
            self._load_project(Path(directory))

    @Slot()
    def _on_visualize_clicked(self) -> None:
        """Handle visualization button click.

        Validates that a project is loaded and channels are selected,
        then emits cleanup_requested followed by visualization_requested
        signals with the current configuration.
        """
        logger.debug("UI Click: Start visualization button")

        if not self._project_data:
            logger.debug("UI Action: No project loaded, showing error")
            self.error_message.emit("No project loaded. Please load a project first.")
            return

        selected_channels = [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._channels_list.selectedItems()
        ]
        if not selected_channels:
            logger.debug("UI Action: No channels selected, showing error")
            self.error_message.emit("No channels selected for visualization.")
            return

        # Emit cleanup signal first to clear existing plots and traces
        logger.debug("UI Event: Emitting cleanup_requested")
        self.cleanup_requested.emit()

        logger.debug(
            "UI Event: Emitting visualization_requested - FOV=%d, channels=%s",
            self._fov_spinbox.value(),
            selected_channels,
        )
        self.visualization_requested.emit(
            self._project_data, self._fov_spinbox.value(), selected_channels
        )

    # ------------------------------------------------------------------------
    # PROJECT LOADING
    # ------------------------------------------------------------------------
    def _load_project(self, project_path: Path) -> None:
        """Load project data from the given path.

        Args:
            project_path: Path to the project directory
        """
        logger.info("Loading project from %s", project_path)
        self.set_loading(True)
        self.project_loading_started.emit()

        try:
            project_data = load_processing_results_yaml(
                project_path / "processing_results.yaml"
            )
            self._project_data = project_data
            self._update_ui_with_project_data(project_data)
            self.project_loaded.emit(project_data)
            self.project_loading_finished.emit(
                True, self._format_project_status(project_data)
            )
        except Exception as exc:
            message = self._format_project_error(project_path, exc)
            logger.exception("Failed to load project")
            self.error_message.emit(message)
            self.project_loading_finished.emit(False, message)
        finally:
            self.set_loading(False)

    # ------------------------------------------------------------------------
    # UI UPDATES
    # ------------------------------------------------------------------------
    def _update_ui_with_project_data(self, project_data: dict) -> None:
        """Update UI elements with loaded project data.

        Args:
            project_data: Dictionary containing project information
        """
        self._set_project_details_text(project_data)

        # Debug: Log FOV data structure
        fov_data = project_data.get("fov_data", {})
        if fov_data:
            first_fov_id = next(iter(fov_data.keys()))
            first_fov_data = fov_data[first_fov_id]
            logger.debug(
                f"First FOV ({first_fov_id}) data keys: {list(first_fov_data.keys())}"
            )

        # Update channel list
        channels = self._extract_available_channels(project_data)
        logger.debug(f"Extracted available channels: {channels}")
        self._channels_list.clear()
        for channel in sorted(channels):
            item = QListWidgetItem(channel)
            item.setData(Qt.ItemDataRole.UserRole, channel)
            self._channels_list.addItem(item)
        self._channels_list.setVisible(bool(channels))
        self._visualize_button.setVisible(bool(channels))

        # Update FOV range
        fov_keys = list(project_data.get("fov_data", {}).keys())
        min_fov, max_fov = (min(fov_keys), max(fov_keys)) if fov_keys else (0, 0)
        self._fov_spinbox.setRange(min_fov, max_fov)
        self._fov_max_label.setText(f"/ {max_fov}")
        self._channels_list.clearSelection()

    def _set_project_details_text(self, project_data: dict) -> None:
        """Set the project details text in the UI.

        Args:
            project_data: Dictionary containing project information
        """
        details = [
            f"Project Path: {project_data.get('project_path', 'Unknown')}",
            f"FOVs: {project_data.get('n_fov', 0)}",
        ]

        if time_units := project_data.get("time_units"):
            details.append(f"Time Units: {time_units}")

        if project_data.get("fov_data"):
            first_fov = next(iter(project_data["fov_data"].values()))
            details.append("Available Data:")
            details.extend([f"   • {dt}" for dt in first_fov.keys()])

        self._project_details_text.setPlainText("\n".join(details))

    # ------------------------------------------------------------------------
    # UTILITY METHODS
    # ------------------------------------------------------------------------
    @staticmethod
    def _extract_available_channels(project_data: dict) -> list[str]:
        """Extract available channels from project data.

        Args:
            project_data: Dictionary containing project information

        Returns:
            List of available channel names
        """
        if not project_data.get("fov_data"):
            return []
        first_fov = next(iter(project_data["fov_data"].values()))
        channels = [
            k
            for k in first_fov.keys()
            if not k.startswith("traces")  # Only exclude trace CSV files
        ]
        return sorted(channels)

    @staticmethod
    def _format_project_status(project_data: dict) -> str:
        """Format project status for display.

        Args:
            project_data: Dictionary containing project information

        Returns:
            Formatted status string
        """
        n_fov = project_data.get("n_fov", 0)
        project_path = project_data.get("project_path", "unknown folder")
        return f"{n_fov} FOVs loaded from {project_path}"

    @staticmethod
    def _format_project_error(project_path: Path, exc: Exception) -> str:
        """Format project error messages for user display.

        Args:
            project_path: Path to the project directory
            exc: Exception that occurred

        Returns:
            Formatted error message
        """
        msg = str(exc)
        if "No FOV directories found" in msg:
            return f"No data found in {project_path}. Ensure it contains FOV subdirectories."
        return msg
