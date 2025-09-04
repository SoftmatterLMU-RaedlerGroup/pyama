"""
Main window for the PyAMA-Qt Visualization application.
"""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Signal, QThread
from pathlib import Path

from .widgets.image_viewer import ImageViewer
from .widgets.project_loader import ProjectLoader
from .widgets.trace_viewer import TraceViewer
from pyama_core.io.result_loader import discover_processing_results
import logging

logger = logging.getLogger(__name__)
from pyama_core.io.trace_parser import TraceParser
from ..services.preprocessing_worker import PreprocessingWorker


class VisualizationMainWindow(QMainWindow):
    """Main window for visualization application."""

    project_loaded = Signal(dict)  # Emitted when project is loaded

    def __init__(self):
        super().__init__()

        # Set up logging (without Qt handler since we don't have a logger widget yet)
        logging.basicConfig(level=logging.INFO)
        logger.info("Initializing PyAMA-Qt Visualizer")

        self.current_project = None
        # Background worker/thread references
        self._worker_thread: QThread | None = None
        self._worker: PreprocessingWorker | None = None
        # Shared image cache used by worker and viewer
        self._image_cache: dict = {}
        self.setup_ui()
        self.setup_statusbar()

    def setup_ui(self):
        """Set up the main UI layout."""
        self.setWindowTitle("PyAMA-Qt Visualizer")
        self.setMinimumSize(1200, 800)

        # Central widget with splitter layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Left: project loader
        self.project_loader = ProjectLoader()
        self.project_loader.project_loaded.connect(self.on_project_loaded)
        self.project_loader.visualization_requested.connect(
            self.on_visualization_requested
        )
        main_layout.addWidget(self.project_loader, 1)

        # Middle: image viewer
        self.image_viewer = ImageViewer()
        # Provide shared cache reference to image viewer
        self.image_viewer.current_images = self._image_cache
        main_layout.addWidget(self.image_viewer, 3)

        # Right: trace viewer
        self.trace_viewer = TraceViewer()
        # Wire active trace selection to image viewer overlay
        self.trace_viewer.active_trace_changed.connect(
            self.image_viewer.set_active_trace
        )
        main_layout.addWidget(self.trace_viewer, 2)

    def setup_statusbar(self):
        """Set up the status bar."""
        self.statusbar = self.statusBar()
        self.statusbar.showMessage("Ready - Open a data folder to begin visualization")

    def open_project_dialog(self):
        """Open file dialog to select project directory."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setWindowTitle("Select Data Folder")

        if dialog.exec():
            selected_dirs = dialog.selectedFiles()
            if selected_dirs:
                self.load_project(Path(selected_dirs[0]))

    def load_project(self, project_path: Path):
        """
        Load a PyAMA-Qt processing results project.

        Args:
            project_path: Path to the processing results directory
        """
        try:
            self.statusbar.showMessage(f"Loading project: {project_path.name}")

            # Discover processing results
            project_data = discover_processing_results(project_path)

            self.current_project = project_data

            # Show informative status message
            has_project_file = project_data.get("has_project_file", False)
            status = project_data.get("processing_status", "unknown")

            if has_project_file:
                status_msg = f"Project loaded: {project_data['n_fov']} FOVs, Status: {status.title()}"
                if status != "completed":
                    status_msg += " ⚠️"
            else:
                status_msg = f"Project loaded: {project_data['n_fov']} FOVs"

            self.project_loaded.emit(project_data)

            # Update UI - enable viewer tabs but don't load project data into image viewer yet
            self.setWindowTitle(f"PyAMA-Qt Visualizer - {project_path.name}")
            self.statusbar.showMessage(status_msg)

        except Exception as e:
            error_msg = str(e)
            if "No FOV directories found" in error_msg:
                error_msg = f"No data found in {project_path}\\n\\nMake sure you've selected a directory containing FOV subdirectories (fov_0000, fov_0001, etc.)"

            QMessageBox.critical(
                self,
                "Error Loading Project",
                f"Failed to load project from {project_path}:\\n{error_msg}",
            )
            self.statusbar.showMessage("Error loading project")

    def on_project_loaded(self, project_data: dict):
        """Handle project loaded signal from project loader widget."""
        self.current_project = project_data

        # Don't enable image viewer yet - it should only be enabled after FOV data is preloaded
        # self.image_viewer.setEnabled(True)  # This will be enabled when visualization is requested
        self.setWindowTitle("PyAMA-Qt Visualizer")

        # Show informative status message
        has_project_file = project_data.get("has_project_file", False)
        status = project_data.get("processing_status", "unknown")

        if has_project_file:
            status_msg = f"Project loaded: {project_data['n_fov']} FOVs, Status: {status.title()}"
            if status != "completed":
                status_msg += " ⚠️"
        else:
            status_msg = f"Project loaded: {project_data['n_fov']} FOVs"

        self.statusbar.showMessage(status_msg)

    def on_visualization_requested(self, fov_idx: int):
        """Handle visualization requested signal from project loader widget."""
        if self.current_project is not None:
            # Clear shared cache; we only keep current FOV in memory
            self._image_cache.clear()
            # Pass project data and specific FOV index to viewer components only when visualization is requested
            self.image_viewer.load_fov_data(self.current_project, fov_idx)
            # Start background preprocessing in a worker managed by the main window
            self._start_fov_worker(self.current_project, fov_idx)

    def _start_fov_worker(self, project_data: dict, fov_idx: int) -> None:
        """Create and start the preprocessing worker in a background thread."""
        # Clean up any existing worker/thread
        self._cleanup_worker()

        # Create thread and worker
        self._worker_thread = QThread()
        self._worker = PreprocessingWorker(
            project_data, fov_idx, image_cache=self._image_cache
        )
        self._worker.moveToThread(self._worker_thread)

        # Wire signals to the image viewer handlers
        self._worker_thread.started.connect(self._worker.process_fov_data)
        # Route progress to the loader's progress bar
        self._worker.progress_updated.connect(
            self.project_loader.update_progress_message
        )
        self._worker.fov_data_loaded.connect(self.image_viewer._on_fov_data_loaded)
        # Also react here to load traces CSV and populate the trace viewer (limit to first 10 for now)
        self._worker.fov_data_loaded.connect(self._on_fov_ready)
        self._worker.finished.connect(self.image_viewer._on_worker_finished)
        self._worker.error_occurred.connect(self.image_viewer._on_worker_error)

        # Ensure proper thread shutdown and cleanup
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._cleanup_worker)

        # Start and show progress in loader
        self.project_loader.start_progress(f"Loading FOV {fov_idx:04d}...")
        self._worker_thread.start()

    def _cleanup_worker(self) -> None:
        """Tear down worker and thread safely."""
        if self._worker is not None:
            try:
                self._worker.deleteLater()
            finally:
                self._worker = None

        if self._worker_thread is not None:
            try:
                if self._worker_thread.isRunning():
                    self._worker_thread.quit()
                    self._worker_thread.wait()
                self._worker_thread.deleteLater()
            finally:
                self._worker_thread = None
        # Hide progress bar on cleanup
        if hasattr(self, "project_loader") and hasattr(
            self.project_loader, "finish_progress"
        ):
            self.project_loader.finish_progress()

    def _on_fov_ready(self, fov_idx: int) -> None:
        """When a FOV's image data is ready, load its traces CSV and populate the TraceViewer.

        Uses the new TraceParser to extract both intensity and area data.
        """
        try:
            if self.current_project is None:
                self.trace_viewer.clear()
                return
            fov_catalog = self.current_project.get("fov_data", {})
            fov_entry = fov_catalog.get(fov_idx, {})
            traces_path = fov_entry.get("traces")

            if traces_path is None:
                # No traces for this FOV
                self.trace_viewer.clear()
                # Clear overlay positions and active trace
                self.image_viewer.set_trace_positions({})
                self.image_viewer.set_active_trace(None)
                return

            # Use the new TraceParser to parse the CSV
            trace_data = TraceParser.parse_csv(traces_path)

            # Provide CSV path to trace viewer so it can save inspected labels
            self.trace_viewer.set_traces_csv_path(traces_path)

            if not trace_data.unique_ids:
                # No valid data found
                self.trace_viewer.clear()
                self.image_viewer.set_trace_positions({})
                self.image_viewer.set_active_trace(None)
                return

            # Check if we have time series data
            if trace_data.frames_axis.size == 0:
                # No frame data, just show IDs with good status
                self.trace_viewer.set_traces(
                    trace_data.unique_ids, trace_data.good_status
                )
                self.image_viewer.set_trace_positions(
                    trace_data.positions.cell_positions
                )
                self.image_viewer.set_active_trace(None)
                return

            # Pass dynamic feature series to the viewer
            self.trace_viewer.set_trace_data(
                trace_data.unique_ids,
                trace_data.frames_axis,
                trace_data.feature_series,
                trace_data.good_status,
            )

            # Set positions for overlay
            self.image_viewer.set_trace_positions(trace_data.positions.cell_positions)
            # Reset active highlight on new FOV
            self.image_viewer.set_active_trace(None)

        except Exception:
            # On any error, keep the UI stable and clear the trace viewer
            self.trace_viewer.clear()
            self.image_viewer.set_trace_positions({})
            self.image_viewer.set_active_trace(None)

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About PyAMA-Qt Visualizer",
            "PyAMA-Qt Visualizer\\n\\n"
            "Interactive visualization and analysis of microscopy processing results.\\n\\n"
            "Part of the PyAMA-Qt microscopy image analysis suite.",
        )

    def closeEvent(self, event):
        """Handle application close event."""
        # Ensure background worker is cleaned up before exit
        self._cleanup_worker()
        event.accept()
