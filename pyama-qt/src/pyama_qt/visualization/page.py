"""
Main window for the PyAMA-Qt Visualization application.
"""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QMessageBox,
    QFileDialog,
    QStatusBar,
)
from PySide6.QtCore import Signal, QThread, QObject
from pathlib import Path

from .widgets import ImagePanel, ProjectPanel, TracePanel
from pyama_core.io.result_loader import discover_processing_results
import numpy as np
import logging

from pyama_core.io import TraceParser

logger = logging.getLogger(__name__)


class PreprocessingWorker(QObject):
    """Worker class for preprocessing FOV data in a background thread."""

    # Signals for communication with the main thread
    progress_updated = Signal(str)  # Message about current progress
    fov_data_loaded = Signal(
        int
    )  # Emitted when FOV data is loaded and preprocessed (FOV index only)
    finished = Signal()  # Emitted when all processing is complete
    error_occurred = Signal(str)  # Emitted when an error occurs

    def __init__(
        self, project_data: dict, fov_idx: int, image_cache: dict | None = None
    ):
        """
        Initialize the worker.

        Args:
            project_data: Project data dictionary
            fov_idx: Index of the FOV to process
        """
        super().__init__()
        self.project_data = project_data
        self.fov_idx = fov_idx
        # Use shared image cache if provided (owned by main window)
        self.current_images = image_cache if image_cache is not None else {}

    def process_fov_data(self):
        """Process FOV data in the background thread."""
        try:
            self.progress_updated.emit(f"Loading data for FOV {self.fov_idx:04d}...")

            if self.fov_idx not in self.project_data["fov_data"]:
                self.error_occurred.emit(
                    f"FOV {self.fov_idx} not found in project data"
                )
                return

            fov_data = self.project_data["fov_data"][self.fov_idx]

            # Clear shared cache entirely; it only stores current FOV
            try:
                self.current_images.clear()
            except Exception:
                # Fallback in case it's not a standard dict-like
                for key in list(self.current_images.keys()):
                    self.current_images.pop(key, None)
            image_types = [k for k in fov_data.keys() if k != "traces"]

            logger.info(
                f"Preloading {len(image_types)} data types for FOV {self.fov_idx}"
            )
            self.progress_updated.emit(
                f"Preloading {len(image_types)} data types for FOV {self.fov_idx}..."
            )

            # Load and preprocess all image data
            for i, data_type in enumerate(sorted(image_types)):
                try:
                    self.progress_updated.emit(
                        f"Loading {data_type} ({i + 1}/{len(image_types)})..."
                    )
                    image_path = fov_data[data_type]

                    # Use memory mapping for efficient loading of NPY files
                    image_data = np.load(image_path, mmap_mode="r")

                    # Preprocess data for visualization (normalize to uint8)
                    self.progress_updated.emit(
                        f"Preprocessing {data_type} ({i + 1}/{len(image_types)})..."
                    )
                    processed_data = self._preprocess_for_visualization(
                        image_data, data_type
                    )

                    # Store by data_type only; cache represents current FOV
                    self.current_images[data_type] = processed_data
                    logger.info(
                        f"Preloaded and processed {data_type} data: shape {processed_data.shape}, dtype {processed_data.dtype}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error preloading {data_type} data for FOV {self.fov_idx}: {e}"
                    )
                    # Continue with other data types even if one fails
                    continue

            logger.info(f"Completed preloading data for FOV {self.fov_idx}")
            self.progress_updated.emit(
                f"Completed preloading data for FOV {self.fov_idx}"
            )

            # Notify listeners that this FOV's data is ready in the shared cache
            self.fov_data_loaded.emit(self.fov_idx)

        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()

    def _preprocess_for_visualization(
        self, image_data: np.ndarray, data_type: str
    ) -> np.ndarray:
        """
        Preprocess image data for visualization by normalizing to uint8.

        Args:
            image_data: Input image data
            data_type: Type of data (for special handling)

        Returns:
            Preprocessed image data as uint8
        """
        # Handle different data types
        if (
            image_data.dtype == np.bool_
            or image_data.dtype == bool
            or "binarized" in data_type
        ):
            # Binary image - convert to uint8 directly
            return (image_data * 255).astype(np.uint8)
        else:
            # For other data types, normalize to uint8
            # Calculate 1st and 99th percentiles for normalization
            data_min = np.nanpercentile(image_data, 0.01)
            data_max = np.nanpercentile(image_data, 99.99)

            # Avoid division by zero
            if data_max > data_min:
                # Normalize to 0-255 range
                normalized = (
                    (image_data - data_min) / (data_max - data_min) * 255
                ).astype(np.uint8)
            else:
                normalized = np.zeros_like(image_data, dtype=np.uint8)

            return normalized


class VisualizationPage(QWidget):
    """Embeddable visualization page (QWidget) with full UI and logic."""

    project_loaded = Signal(dict)  # Emitted when project is loaded

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # Set up logging (without Qt handler since we don't have a logger widget yet)
        logging.basicConfig(level=logging.INFO)

        self.current_project = None
        # Background worker/thread references
        self._worker_thread: QThread | None = None
        self._worker: PreprocessingWorker | None = None
        # Shared image cache used by worker and viewer
        self._image_cache: dict = {}
        self.setup_ui()

        logger.info("PyAMA Visualization Page loaded")

    def setup_ui(self):
        """Set up the main UI layout inside this widget."""
        # Central widget layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Left: project loader
        self.project_loader = ProjectPanel()
        self.project_loader.project_loaded.connect(self.on_project_loaded)
        self.project_loader.visualization_requested.connect(
            self.on_visualization_requested
        )
        main_layout.addWidget(self.project_loader, 1)

        # Middle: image viewer
        self.image_viewer = ImagePanel()
        # Provide shared cache reference to image viewer
        self.image_viewer.current_images = self._image_cache
        main_layout.addWidget(self.image_viewer, 3)

        # Right: trace viewer
        self.trace_viewer = TracePanel()
        # Wire active trace selection to image viewer overlay
        self.trace_viewer.active_trace_changed.connect(
            self.image_viewer.set_active_trace
        )
        main_layout.addWidget(self.trace_viewer, 2)

        # Embedded status bar at bottom (optional)
        self.statusbar = QStatusBar(self)
        self.statusbar.showMessage("Ready - Open a data folder to begin visualization")
        main_layout.addWidget(self.statusbar)

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

            # Update UI status only (no window title here)
            self.statusbar.showMessage(status_msg)

        except Exception as e:
            error_msg = str(e)
            if "No FOV directories found" in error_msg:
                error_msg = f"No data found in {project_path}\n\nMake sure you've selected a directory containing FOV subdirectories (fov_0000, fov_0001, etc.)"

            QMessageBox.critical(
                self,
                "Error Loading Project",
                f"Failed to load project from {project_path}:\n{error_msg}",
            )
            self.statusbar.showMessage("Error loading project")

    def on_project_loaded(self, project_data: dict):
        """Handle project loaded signal from project loader widget."""
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

        self.statusbar.showMessage(status_msg)

    def on_visualization_requested(self, fov_idx: int):
        """Handle visualization requested signal from project loader widget."""
        if self.current_project is not None:
            # Clear shared cache; we only keep current FOV in memory
            self._image_cache.clear()
            # Pass project data and specific FOV index to viewer components only when visualization is requested
            self.image_viewer.load_fov_data(self.current_project, fov_idx)
            # Start background preprocessing in a worker managed by the page
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


class VisualizationMainWindow(QMainWindow):
    """Standalone wrapper to host VisualizationPage for backward compatibility."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyAMA-Qt Visualizer")
        self.setMinimumSize(1200, 800)
        self.setCentralWidget(VisualizationPage(self))
