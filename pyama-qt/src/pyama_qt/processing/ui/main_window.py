"""
Main window for PyAMA-Qt processing application.
"""

from pathlib import Path
import logging

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QStatusBar,
    QProgressBar,
)
from PySide6.QtCore import QThread, QObject, Signal
from typing import Any
from pyama_core.io.nikon import ND2Metadata

from ..services.workflow import ProcessingWorkflow

from .widgets import Workflow
from .widgets import FileLoader

logger = logging.getLogger(__name__)


class WorkflowWorker(QObject):
    """Worker class for running workflow processing in a separate thread."""

    finished = Signal(bool, str)  # success, message

    def __init__(
        self,
        workflow_coordinator: ProcessingWorkflow,
        metadata: ND2Metadata,
        context: dict[str, Any],
        fov_start: int,
        fov_end: int | None,
        batch_size: int,
        n_workers: int,
    ):
        super().__init__()
        self.workflow_coordinator = workflow_coordinator
        self.metadata = metadata
        self.context = context
        self.fov_start = fov_start
        self.fov_end = fov_end
        self.batch_size = batch_size
        self.n_workers = n_workers

    def run_processing(self):
        """Run the workflow processing."""
        try:
            success = self.workflow_coordinator.run_complete_workflow(
                self.metadata,
                self.context,
                fov_start=self.fov_start,
                fov_end=self.fov_end,
                batch_size=self.batch_size,
                n_workers=self.n_workers,
            )

            if success:
                self.finished.emit(True, f"Results saved to {self.context.get('output_dir')}")
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

        logging.basicConfig(level=logging.INFO)

        self.setup_ui()
        self.setup_status_bar()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.file_loader = FileLoader()
        main_layout.addWidget(self.file_loader)

        self.workflow = Workflow()
        main_layout.addWidget(self.workflow)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate by default
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        main_layout.addStretch()

        self.workflow_coordinator = ProcessingWorkflow(self)

        self.file_loader.data_loaded.connect(self.on_data_loaded)
        self.file_loader.status_message.connect(self.update_status)
        self.workflow.process_requested.connect(self.start_workflow_processing)

        logger.info("PyAMA Processing Tool ready")

    def setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def on_data_loaded(self, data_info):
        filepath = data_info["filepath"]
        logger.info(f"ND2 file loaded: {filepath}")
        self.status_bar.showMessage(f"Loaded: {filepath}")
        self.workflow.set_data_available(True, data_info)

    def start_workflow_processing(self, params):
        self.processing_thread = QThread()
        # Build ND2Metadata from UI-provided data_info
        di = params["data_info"]
        md = ND2Metadata(
            nd2_path=Path(di["filepath"]),
            base_name=di["filename"].replace(".nd2", ""),
            height=int(di.get("height", 0)),
            width=int(di.get("width", 0)),
            n_frames=int(di.get("n_frames", 0)),
            n_fovs=int(di.get("n_fov", 0)),
            n_channels=len(di.get("channels", [])),
            timepoints=[float(i) for i in range(int(di.get("n_frames", 0)))],
            channel_names=list(di.get("channels", [])),
            dtype=str(di.get("dtype", "uint16")),
        )

        self.workflow_worker = WorkflowWorker(
            self.workflow_coordinator,
            md,
            {
                "output_dir": params["output_dir"],
                "params": params,
                "channels": {
                    "phase_contrast": di.get("pc_channel"),
                    "fluorescence": di.get("fl_channel"),
                },
                "npy_paths": {},
            },
            params.get("fov_start", 0),
            params.get("fov_end"),
            params.get("batch_size", 4),
            params.get("n_workers", 4),
        )
        self.workflow_worker.moveToThread(self.processing_thread)

        self.processing_thread.started.connect(self.workflow_worker.run_processing)
        self.workflow_worker.finished.connect(self.on_processing_finished)
        self.workflow_worker.finished.connect(self.processing_thread.quit)
        self.workflow_worker.finished.connect(self.workflow_worker.deleteLater)
        self.processing_thread.finished.connect(self.processing_thread.deleteLater)

        self.processing_thread.start()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.show()
        self.update_status("Workflow processing started...")

    def on_processing_finished(self, success, message):
        self.workflow.processing_finished(success, message)
        if success:
            self.progress_bar.hide()
            self.update_status("Workflow completed successfully")
        else:
            self.progress_bar.hide()
            self.update_status(f"Workflow failed: {message}")

    def on_workflow_error(self, error_message):
        self.workflow.processing_error(error_message)
        self.update_status(f"Error: {error_message}")

    def update_status(self, message):
        self.status_bar.showMessage(message)

    def update_progress(self, value):
        if value < 0:
            self.progress_bar.setRange(0, 0)  # Indeterminate
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)

    def closeEvent(self, event):
        super().closeEvent(event)
