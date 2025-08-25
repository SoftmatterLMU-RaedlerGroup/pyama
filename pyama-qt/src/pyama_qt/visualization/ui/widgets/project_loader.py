"""
Project loader widget for the visualization application.
This widget provides a simplified interface for loading FOV data from folders.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
)
from PySide6.QtCore import Signal, Qt
from pathlib import Path

from pyama_core.io.result_loader import discover_processing_results
from pyama_qt.utils.logging_config import get_logger


class ProjectLoader(QWidget):
    """Widget for loading and displaying FOV data from folders."""

    project_loaded = Signal(dict)  # Emitted when project is successfully loaded
    visualization_requested = Signal(
        int
    )  # Emitted when visualization is requested for an FOV

    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        self.current_project = None
        self.selected_fov = None
        self.visualization_started = False
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Project loading controls
        controls_group = QGroupBox("Load Data Folder")
        controls_layout = QVBoxLayout(controls_group)

        # Load button
        self.load_button = QPushButton("Load Folder...")
        self.load_button.clicked.connect(self.load_folder_dialog)
        self.load_button.setToolTip("Load a folder containing FOV subdirectories")
        controls_layout.addWidget(self.load_button)

        # FOV list
        fov_label = QLabel("Fields of View:")
        controls_layout.addWidget(fov_label)

        self.fov_list = QListWidget()
        self.fov_list.itemClicked.connect(self.on_fov_selected)
        self.fov_list.setMinimumHeight(100)
        controls_layout.addWidget(self.fov_list)

        layout.addWidget(controls_group)

        # Data display group
        data_group = QGroupBox("Available NPY Files")
        data_layout = QVBoxLayout(data_group)

        self.npy_list = QListWidget()
        data_layout.addWidget(self.npy_list)

        # Visualization button
        self.visualize_button = QPushButton("Start Visualization")
        self.visualize_button.clicked.connect(self.on_visualize_clicked)
        self.visualize_button.setEnabled(False)
        data_layout.addWidget(self.visualize_button)

        # Progress bar for background preprocessing (managed by main window)
        # Always visible: idle when not processing, indeterminate when processing
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)  # Idle state
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_bar.setTextVisible(False)
        data_layout.addWidget(self.progress_bar)

        layout.addWidget(data_group)

        # Initially disable data group
        data_group.setEnabled(False)

        self.data_group = data_group

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
            self.logger.info(f"Loading folder: {folder_path}")

            # Discover processing results
            project_data = discover_processing_results(folder_path)

            self.current_project = project_data
            self.logger.info(
                f"Successfully loaded project with {project_data['n_fov']} FOVs"
            )

            # Update FOV list
            self.update_fov_list(project_data)

            # Enable displays
            self.data_group.setEnabled(True)

            # Emit signal
            self.project_loaded.emit(project_data)

        except Exception as e:
            self.logger.error(f"Failed to load data from {folder_path}: {str(e)}")
            QMessageBox.critical(
                self,
                "Error Loading Data",
                f"Failed to load data from {folder_path}:\\n{str(e)}",
            )

    def update_fov_list(self, project_data: dict):
        """Update the FOV list widget."""
        self.fov_list.clear()

        for fov_idx in sorted(project_data["fov_data"].keys()):
            item = QListWidgetItem(f"FOV {fov_idx:04d}")
            item.setData(Qt.ItemDataRole.UserRole, fov_idx)
            self.fov_list.addItem(item)

    def on_fov_selected(self, item):
        """Handle FOV selection."""
        if item is None or self.current_project is None:
            return

        fov_idx = item.data(Qt.ItemDataRole.UserRole)
        fov_data = self.current_project["fov_data"][fov_idx]

        # Update npy files list
        self.npy_list.clear()
        for data_type, file_path in sorted(fov_data.items()):
            # Only show npy files
            if file_path.suffix.lower() == ".npy":
                item = QListWidgetItem(file_path.name)
                item.setData(Qt.ItemDataRole.UserRole, file_path)
                self.npy_list.addItem(item)

        # Enable visualization button
        self.visualize_button.setEnabled(True)

        # Reset visualization state when FOV changes
        self.selected_fov = fov_idx
        self.visualization_started = False
        self.visualize_button.setText("Start Visualization")

    # Progress bar control methods (used by main window)
    def start_progress(self, message: str) -> None:
        self.progress_bar.setRange(0, 0)  # Indeterminate/busy

    def update_progress_message(self, message: str) -> None:
        pass

    def finish_progress(self) -> None:
        # Return to idle state but keep visible
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)

    def on_visualize_clicked(self):
        """Handle visualization button click."""
        if self.selected_fov is not None:
            if not self.visualization_started:
                # Start visualization
                self.visualization_requested.emit(self.selected_fov)
                self.visualization_started = True
                self.visualize_button.setText("Visualization Started")
            else:
                # Reset visualization state
                self.visualization_started = False
                self.visualize_button.setText("Start Visualization")
