"""
Main window for PyAMA-Qt processing application.
"""

from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStatusBar
from PySide6.QtCore import QThread, QObject, Signal

from .widgets.fileloader import FileLoader
from .widgets.workflow import Workflow
from ..services.workflow import WorkflowCoordinator
from pyama_qt.core.logging_config import setup_logging, get_logger


class WorkflowWorker(QObject):
    """Worker class for running workflow processing in a separate thread."""

    finished = Signal(bool, str)  # success, message

    def __init__(self, workflow_coordinator, nd2_path, data_info, output_dir, params):
        super().__init__()
        self.workflow_coordinator = workflow_coordinator
        self.nd2_path = nd2_path
        self.data_info = data_info
        self.output_dir = output_dir
        self.params = params

    def run_processing(self):
        """Run the workflow processing."""
        try:
            # Extract FOV and batch parameters
            fov_start = self.params.get("fov_start", 0)
            fov_end = self.params.get("fov_end", None)
            batch_size = self.params.get("batch_size", 4)
            n_workers = self.params.get("n_workers", 4)

            success = self.workflow_coordinator.run_complete_workflow(
                self.nd2_path,
                self.data_info,
                self.output_dir,
                self.params,
                fov_start=fov_start,
                fov_end=fov_end,
                batch_size=batch_size,
                n_workers=n_workers,
            )

            if success:
                self.finished.emit(True, f"Results saved to {self.output_dir}")
            else:
                self.finished.emit(False, "Workflow failed")

        except Exception as e:
            self.finished.emit(False, f"Workflow error: {str(e)}")


class MainWindow(QMainWindow):
    """Main application window for PyAMA-Qt processing tool."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyAMA Processing Tool")
        self.setGeometry(100, 100, 400, 600)

        # Set up logging with Qt handler
        self.qt_log_handler = setup_logging(use_qt_handler=True)
        self.logger = get_logger(__name__)

        self.setup_ui()
        self.setup_status_bar()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # File loading section
        self.file_loader = FileLoader()
        main_layout.addWidget(self.file_loader)

        # Workflow settings (output dir and start button)
        self.workflow = Workflow()
        main_layout.addWidget(self.workflow)

        # Add stretch to push widgets to top
        main_layout.addStretch()

        # Initialize workflow coordinator
        self.workflow_coordinator = WorkflowCoordinator(self)
        self.setup_workflow_connections()

        # Connect signals
        self.file_loader.data_loaded.connect(self.on_data_loaded)
        self.file_loader.status_message.connect(self.update_status)
        self.workflow.process_requested.connect(self.start_workflow_processing)

        # Log initial ready state
        self.logger.info("PyAMA Processing Tool ready")

    def setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def load_nd2_file(self):
        self.file_loader.select_nd2_file()

    def show_about(self):
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.about(
            self,
            "About PyAMA Processing Tool",
            "PyAMA Processing Tool v0.1.0\\n\\n"
            "Image processing tools for microscopy data\\n"
            "Features binarization and background correction",
        )

    def on_data_loaded(self, data_info):
        """Handle when data is successfully loaded"""
        filepath = data_info["filepath"]
        self.logger.info(f"ND2 file loaded: {filepath}")
        self.status_bar.showMessage(f"Loaded: {filepath}")

        # Enable processing workflow
        self.workflow.set_data_available(True, data_info)

    def setup_workflow_connections(self):
        """Connect workflow coordinator signals to UI updates"""
        services = self.workflow_coordinator.get_all_services()

        for service in services:
            service.progress_updated.connect(self.workflow.update_progress)
            service.status_updated.connect(self.update_workflow_status)
            service.error_occurred.connect(self.on_workflow_error)

    def start_workflow_processing(self, params):
        """Start workflow processing in a separate thread"""
        # Extract parameters
        nd2_path = params["data_info"]["filepath"]
        data_info = params["data_info"]
        output_dir = Path(params["output_dir"])

        # Create worker and thread
        self.processing_thread = QThread()
        self.workflow_worker = WorkflowWorker(
            self.workflow_coordinator, nd2_path, data_info, output_dir, params
        )

        # Move worker to thread
        self.workflow_worker.moveToThread(self.processing_thread)

        # Connect signals
        self.processing_thread.started.connect(self.workflow_worker.run_processing)
        self.workflow_worker.finished.connect(self.on_processing_finished)
        self.workflow_worker.finished.connect(self.processing_thread.quit)
        self.workflow_worker.finished.connect(self.workflow_worker.deleteLater)
        self.processing_thread.finished.connect(self.processing_thread.deleteLater)

        # Start processing
        self.processing_thread.start()

        # Log workflow start
        fov_start = params.get("fov_start", 0)
        fov_end = params.get("fov_end", None)
        batch_size = params.get("batch_size", 4)
        n_workers = params.get("n_workers", 4)

        fov_range = f"{fov_start}-{fov_end if fov_end is not None else 'all'}"
        self.logger.info(f"Starting workflow processing (FOV {fov_range})")
        self.logger.info(f"Output directory: {output_dir}")
        self.logger.info(f"Batch size: {batch_size}, Workers: {n_workers}")

        # Log expected output dtypes
        self.logger.info("Expected output data types:")
        self.logger.info("  - Raw phase contrast (*_phase_contrast_raw.npy): uint16")
        self.logger.info("  - Raw fluorescence (*_fluorescence_raw.npy): uint16")
        self.logger.info("  - Binarized (*_binarized.npy): bool")
        self.logger.info(
            "  - Corrected fluorescence (*_fluorescence_corrected.npy): float32"
        )
        self.logger.info("  - Traces (*_traces.csv): CSV file")

        self.update_status(f"Starting workflow processing (FOV {fov_range})...")

    def on_processing_finished(self, success, message):
        """Handle when workflow processing finishes"""
        self.workflow.processing_finished(success, message)
        if success:
            self.update_status("Workflow completed successfully")
        else:
            self.update_status(f"Workflow failed: {message}")

    def update_workflow_status(self, message):
        """Update workflow status and main status bar"""
        self.update_status(message)

    def on_workflow_error(self, error_message):
        """Handle workflow processing errors"""
        self.workflow.processing_error(error_message)
        self.update_status(f"Error: {error_message}")

    def update_status(self, message):
        """Update status bar message"""
        self.status_bar.showMessage(message)

    def closeEvent(self, event):
        """Handle application close"""
        super().closeEvent(event)
