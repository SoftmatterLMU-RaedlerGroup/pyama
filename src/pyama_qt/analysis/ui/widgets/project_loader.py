"""
Project loader widget for the analysis application.

Provides interface for loading data folders containing FOV trace files.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QTextEdit,
    QSplitter,
)
from PySide6.QtCore import Signal, Qt
from pathlib import Path

from ...services.fitting_worker import discover_trace_files
from pyama_qt.core.logging_config import get_logger


class ProjectLoader(QWidget):
    """Widget for loading and displaying trace data from FOV folders."""

    project_loaded = Signal(dict)  # Emitted when project is successfully loaded
    analysis_requested = Signal(Path, dict)  # Emitted when analysis is requested

    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        self.current_project_path = None
        self.trace_files = {}
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Project loading controls
        controls_group = QGroupBox("Load Project Folder")
        controls_layout = QVBoxLayout(controls_group)

        # Load button and path display
        load_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Folder...")
        self.load_button.clicked.connect(self.load_folder_dialog)
        self.load_button.setToolTip(
            "Load a folder containing FOV subdirectories with trace files"
        )
        load_layout.addWidget(self.load_button)

        self.path_label = QLabel("No folder selected")
        self.path_label.setStyleSheet("QLabel { color: gray; font-style: italic; }")
        load_layout.addWidget(self.path_label, 1)

        controls_layout.addLayout(load_layout)
        layout.addWidget(controls_group)

        # Split view: FOV list and file details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: FOV list
        fov_group = QGroupBox("Fields of View")
        fov_layout = QVBoxLayout(fov_group)

        self.fov_list = QListWidget()
        self.fov_list.itemClicked.connect(self.on_fov_selected)
        self.fov_list.setMinimumHeight(200)
        fov_layout.addWidget(self.fov_list)

        # Summary info
        self.summary_label = QLabel("No data loaded")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fov_layout.addWidget(self.summary_label)

        splitter.addWidget(fov_group)

        # Right side: File details and analysis controls
        details_group = QGroupBox("Details")
        details_layout = QVBoxLayout(details_group)

        # File details area
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setPlainText("Select a FOV to view details")
        details_layout.addWidget(self.details_text)

        # Analysis controls
        analysis_group = QGroupBox("Analysis")
        analysis_layout = QVBoxLayout(analysis_group)

        # Model selection
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))

        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        analysis_layout.addWidget(self.progress_bar)

        # Start analysis button
        self.analyze_button = QPushButton("Start Analysis")
        self.analyze_button.clicked.connect(self.on_analyze_clicked)
        self.analyze_button.setEnabled(False)
        self.analyze_button.setToolTip("Start trace fitting analysis on all FOVs")
        analysis_layout.addWidget(self.analyze_button)

        details_layout.addWidget(analysis_group)
        details_group.setEnabled(False)
        self.details_group = details_group

        splitter.addWidget(details_group)
        splitter.setSizes([300, 400])  # Give more space to details

        layout.addWidget(splitter, 1)

    def load_folder_dialog(self):
        """Open dialog to select project folder."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setWindowTitle("Select Project Folder")

        if dialog.exec():
            selected_dirs = dialog.selectedFiles()
            if selected_dirs:
                self.load_folder(Path(selected_dirs[0]))

    def load_folder(self, folder_path: Path):
        """
        Load project data from folder.

        Args:
            folder_path: Path to folder containing FOV subdirectories
        """
        try:
            self.logger.info(f"Loading project folder: {folder_path}")

            # Discover trace files
            self.trace_files = discover_trace_files(folder_path)

            if not self.trace_files:
                QMessageBox.warning(
                    self,
                    "No Trace Files Found",
                    f"No trace CSV files found in {folder_path}\\n\\n"
                    "Expected structure:\\n"
                    "project_folder/\\n"
                    "  fov_0000/\\n"
                    "    *_traces.csv\\n"
                    "  fov_0001/\\n"
                    "    *_traces.csv\\n"
                    "  ...",
                )
                return

            self.current_project_path = folder_path
            self.path_label.setText(str(folder_path))
            self.path_label.setStyleSheet("")  # Remove gray styling

            # Populate FOV list
            self.populate_fov_list()

            # Update summary
            self.update_summary()

            # Enable controls
            self.details_group.setEnabled(True)
            self.analyze_button.setEnabled(True)

            # Emit project loaded signal
            project_info = {
                "path": folder_path,
                "trace_files": self.trace_files,
                "n_fovs": len(self.trace_files),
            }
            self.project_loaded.emit(project_info)

            self.logger.info(
                f"Successfully loaded project with {len(self.trace_files)} FOVs"
            )

        except Exception as e:
            error_msg = f"Error loading folder: {str(e)}"
            self.logger.error(error_msg)
            QMessageBox.critical(self, "Load Error", error_msg)

    def populate_fov_list(self):
        """Populate the FOV list widget with discovered FOVs."""
        self.fov_list.clear()

        # Sort FOV names naturally
        fov_names = sorted(self.trace_files.keys())

        for fov_name in fov_names:
            item = QListWidgetItem(fov_name)

            # Add trace file info as tooltip
            trace_path = self.trace_files[fov_name]
            item.setToolTip(f"Trace file: {trace_path.name}")

            self.fov_list.addItem(item)

    def update_summary(self):
        """Update the summary label with project statistics."""
        if not self.trace_files:
            self.summary_label.setText("No data loaded")
            return

        n_fovs = len(self.trace_files)
        summary = f"{n_fovs} FOVs with trace files"
        self.summary_label.setText(summary)

    def on_fov_selected(self, item: QListWidgetItem):
        """Handle FOV selection in the list."""
        fov_name = item.text()
        trace_path = self.trace_files.get(fov_name)

        if not trace_path:
            return

        # Display file details
        details_text = f"FOV: {fov_name}\\n"
        details_text += f"Trace file: {trace_path.name}\\n"
        details_text += f"Full path: {trace_path}\\n"

        # Try to get basic file info
        try:
            import pandas as pd

            df = pd.read_csv(trace_path)

            details_text += "\\nFile statistics:\\n"
            details_text += f"  Rows: {len(df):,}\\n"
            details_text += f"  Columns: {len(df.columns)}\\n"

            if "cell_id" in df.columns:
                n_cells = df["cell_id"].nunique()
                details_text += f"  Unique cells: {n_cells}\\n"

            if "frame" in df.columns:
                n_frames = df["frame"].nunique()
                details_text += f"  Time points: {n_frames}\\n"

            # Show column names
            details_text += f"\\nColumns: {', '.join(df.columns)}\\n"

        except Exception as e:
            details_text += f"\\nError reading file: {str(e)}"

        self.details_text.setPlainText(details_text)

    def on_analyze_clicked(self):
        """Handle analysis button click."""
        if not self.current_project_path or not self.trace_files:
            QMessageBox.warning(
                self, "No Project", "Please load a project folder first."
            )
            return

        # For now, emit with default parameters
        # TODO: Add parameter configuration dialog
        analysis_params = {
            "model_type": "maturation",
            "fitting_params": {"n_starts": 10, "noise_level": 0.1, "model_params": {}},
            "batch_size": 10,
            "n_workers": 4,
        }

        self.analysis_requested.emit(self.current_project_path, analysis_params)

    def set_progress(self, value: int):
        """Set progress bar value."""
        if not self.progress_bar.isVisible():
            self.progress_bar.setVisible(True)
        self.progress_bar.setValue(value)

    def hide_progress(self):
        """Hide the progress bar."""
        self.progress_bar.setVisible(False)

    def set_analysis_enabled(self, enabled: bool):
        """Enable or disable analysis controls."""
        self.analyze_button.setEnabled(enabled)

    def clear(self):
        """Clear all loaded data."""
        self.current_project_path = None
        self.trace_files.clear()
        self.fov_list.clear()
        self.details_text.setPlainText("Select a FOV to view details")
        self.summary_label.setText("No data loaded")
        self.path_label.setText("No folder selected")
        self.path_label.setStyleSheet("QLabel { color: gray; font-style: italic; }")
        self.details_group.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.hide_progress()
