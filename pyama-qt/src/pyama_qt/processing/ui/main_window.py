'''
Main window for PyAMA-Qt processing application.
'''

from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStatusBar
from PySide6.QtCore import QThread

from .widgets.fileloader import FileLoader
from .widgets.workflow import Workflow
from ..services.workflow import ProcessingWorkflowCoordinator
from pyama_qt.utils.logging_config import setup_logging, get_logger
from .workers import WorkflowWorker
from pyama_qt.widgets.progress_indicator import ProgressIndicator


class MainWindow(QMainWindow):
    """Main application window for PyAMA-Qt processing tool."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyAMA Processing Tool")
        self.setGeometry(100, 100, 400, 600)

        self.qt_log_handler = setup_logging(use_qt_handler=True)
        self.logger = get_logger(__name__)

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

        self.progress_indicator = ProgressIndicator()
        main_layout.addWidget(self.progress_indicator)

        main_layout.addStretch()

        self.workflow_coordinator = ProcessingWorkflowCoordinator(self)
        self.setup_workflow_connections()

        self.file_loader.data_loaded.connect(self.on_data_loaded)
        self.file_loader.status_message.connect(self.update_status)
        self.workflow.process_requested.connect(self.start_workflow_processing)

        self.logger.info("PyAMA Processing Tool ready")

    def setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def on_data_loaded(self, data_info):
        filepath = data_info["filepath"]
        self.logger.info(f"ND2 file loaded: {filepath}")
        self.status_bar.showMessage(f"Loaded: {filepath}")
        self.workflow.set_data_available(True, data_info)

    def setup_workflow_connections(self):
        services = self.workflow_coordinator.get_all_services()
        for service in services:
            service.progress_updated.connect(self.progress_indicator.set_value)
            service.status_updated.connect(self.progress_indicator.set_text)
            service.error_occurred.connect(self.on_workflow_error)

    def start_workflow_processing(self, params):
        self.processing_thread = QThread()
        self.workflow_worker = WorkflowWorker(
            self.workflow_coordinator, params["data_info"]["filepath"], params["data_info"], Path(params["output_dir"]), params
        )
        self.workflow_worker.moveToThread(self.processing_thread)

        self.processing_thread.started.connect(self.workflow_worker.run_processing)
        self.workflow_worker.finished.connect(self.on_processing_finished)
        self.workflow_worker.finished.connect(self.processing_thread.quit)
        self.workflow_worker.finished.connect(self.workflow_worker.deleteLater)
        self.processing_thread.finished.connect(self.processing_thread.deleteLater)

        self.processing_thread.start()
        self.progress_indicator.task_started("Workflow processing started...")

    def on_processing_finished(self, success, message):
        self.workflow.processing_finished(success, message)
        if success:
            self.progress_indicator.task_finished("Workflow completed successfully.")
            self.update_status("Workflow completed successfully")
        else:
            self.progress_indicator.task_finished(f"Workflow failed: {message}")
            self.update_status(f"Workflow failed: {message}")

    def on_workflow_error(self, error_message):
        self.workflow.processing_error(error_message)
        self.update_status(f"Error: {error_message}")

    def update_status(self, message):
        self.status_bar.showMessage(message)

    def closeEvent(self, event):
        super().closeEvent(event)