"""
Main window for the analysis application.

Provides interface for trace fitting analysis with parallel processing.
"""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTextEdit,
    QGroupBox,
    QLabel,
    QMessageBox,
    QStatusBar,
    QPushButton,
)
from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QAction, QFont
from pathlib import Path
from typing import Dict, Any

from .widgets.project_loader import ProjectLoader
from ..services.workflow import AnalysisWorkflowCoordinator
from pyama_qt.core.logging_config import get_logger


class AnalysisWorkerThread(QThread):
    """Worker thread for running analysis workflow."""

    def __init__(
        self,
        coordinator: AnalysisWorkflowCoordinator,
        data_folder: Path,
        model_type: str,
        fitting_params: Dict[str, Any],
        batch_size: int,
        n_workers: int,
    ):
        super().__init__()
        self.coordinator = coordinator
        self.data_folder = data_folder
        self.model_type = model_type
        self.fitting_params = fitting_params
        self.batch_size = batch_size
        self.n_workers = n_workers

    def run(self):
        """Run the analysis workflow in a separate thread."""
        self.coordinator.run_fitting_workflow(
            self.data_folder,
            self.model_type,
            self.fitting_params,
            self.batch_size,
            self.n_workers,
        )


class MainWindow(QMainWindow):
    """Main window for trace fitting analysis application."""

    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)

        # Analysis components
        self.workflow_coordinator = None
        self.worker_thread = None
        self.is_analysis_running = False

        # Results tracking
        self.completed_fovs = {}
        self.total_fovs = 0

        self.setup_ui()
        self.setup_menu()
        self.setup_status_bar()

        # Window properties
        self.setWindowTitle("PyAMA-Qt Analysis")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

    def setup_ui(self):
        """Set up the main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Project loader
        self.project_loader = ProjectLoader()
        self.project_loader.project_loaded.connect(self.on_project_loaded)
        self.project_loader.analysis_requested.connect(self.on_analysis_requested)
        splitter.addWidget(self.project_loader)

        # Right side: Results and log
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Results area
        results_group = QGroupBox("Analysis Results")
        results_layout = QVBoxLayout(results_group)

        # Results summary
        self.results_summary = QLabel("No analysis results")
        self.results_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        results_layout.addWidget(self.results_summary)

        # Control buttons
        controls_layout = QHBoxLayout()

        self.cancel_button = QPushButton("Cancel Analysis")
        self.cancel_button.clicked.connect(self.on_cancel_analysis)
        self.cancel_button.setEnabled(False)
        controls_layout.addWidget(self.cancel_button)

        self.export_button = QPushButton("Export Results")
        self.export_button.clicked.connect(self.on_export_results)
        self.export_button.setEnabled(False)
        controls_layout.addWidget(self.export_button)

        controls_layout.addStretch()
        results_layout.addLayout(controls_layout)

        right_layout.addWidget(results_group)

        # Log area
        log_group = QGroupBox("Analysis Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)

        # Use monospace font for log
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_text.setFont(font)

        log_layout.addWidget(self.log_text)

        # Clear log button
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_log_btn)

        right_layout.addWidget(log_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])  # Give more space to results

        layout.addWidget(splitter)

    def setup_menu(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        load_action = QAction("Load Project Folder...", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self.project_loader.load_folder_dialog)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Analysis menu
        analysis_menu = menubar.addMenu("Analysis")

        start_action = QAction("Start Analysis", self)
        start_action.setShortcut("F5")
        start_action.triggered.connect(self.project_loader.on_analyze_clicked)
        analysis_menu.addAction(start_action)

        cancel_action = QAction("Cancel Analysis", self)
        cancel_action.setShortcut("Escape")
        cancel_action.triggered.connect(self.on_cancel_analysis)
        analysis_menu.addAction(cancel_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_status_bar(self):
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def on_project_loaded(self, project_info: Dict[str, Any]):
        """Handle project loading."""
        self.total_fovs = project_info["n_fovs"]
        self.completed_fovs.clear()

        self.log_message(f"Loaded project: {project_info['path']}")
        self.log_message(f"Found {self.total_fovs} FOVs with trace files")

        self.update_results_summary()
        self.status_bar.showMessage(f"Project loaded: {self.total_fovs} FOVs")

    def on_analysis_requested(self, data_folder: Path, analysis_params: Dict[str, Any]):
        """Handle analysis request."""
        if self.is_analysis_running:
            QMessageBox.warning(
                self,
                "Analysis Running",
                "Analysis is already running. Please wait or cancel first.",
            )
            return

        self.start_analysis(data_folder, analysis_params)

    def start_analysis(self, data_folder: Path, analysis_params: Dict[str, Any]):
        """Start the analysis workflow."""
        try:
            # Create workflow coordinator
            self.workflow_coordinator = AnalysisWorkflowCoordinator(self)

            # Connect signals
            self.workflow_coordinator.progress_updated.connect(
                self.project_loader.set_progress
            )
            self.workflow_coordinator.status_updated.connect(self.on_status_updated)
            self.workflow_coordinator.error_occurred.connect(self.on_error_occurred)
            self.workflow_coordinator.fov_completed.connect(self.on_fov_completed)

            # Create and start worker thread
            self.worker_thread = AnalysisWorkerThread(
                self.workflow_coordinator,
                data_folder,
                analysis_params["model_type"],
                analysis_params["fitting_params"],
                analysis_params["batch_size"],
                analysis_params["n_workers"],
            )

            self.worker_thread.finished.connect(self.on_analysis_finished)
            self.worker_thread.start()

            # Update UI state
            self.is_analysis_running = True
            self.project_loader.set_analysis_enabled(False)
            self.cancel_button.setEnabled(True)
            self.export_button.setEnabled(False)

            self.log_message("Analysis started...")
            self.status_bar.showMessage("Analysis running...")

        except Exception as e:
            error_msg = f"Error starting analysis: {str(e)}"
            self.logger.error(error_msg)
            QMessageBox.critical(self, "Analysis Error", error_msg)

    def on_cancel_analysis(self):
        """Cancel the running analysis."""
        if not self.is_analysis_running:
            return

        if self.workflow_coordinator:
            self.workflow_coordinator.cancel_workflow()

        self.log_message("Cancelling analysis...")
        self.status_bar.showMessage("Cancelling...")

    def on_analysis_finished(self):
        """Handle analysis completion."""
        self.is_analysis_running = False

        # Update UI state
        self.project_loader.set_analysis_enabled(True)
        self.project_loader.hide_progress()
        self.cancel_button.setEnabled(False)
        self.export_button.setEnabled(len(self.completed_fovs) > 0)

        # Clean up
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None

        self.workflow_coordinator = None

        self.log_message("Analysis completed")
        self.status_bar.showMessage("Analysis completed")

        self.update_results_summary()

    def on_status_updated(self, message: str):
        """Handle status updates from workflow."""
        self.log_message(message)
        self.status_bar.showMessage(message)

    def on_error_occurred(self, error_message: str):
        """Handle error messages from workflow."""
        self.log_message(f"ERROR: {error_message}")

    def on_fov_completed(self, fov_name: str, fov_result: Dict[str, Any]):
        """Handle FOV completion."""
        self.completed_fovs[fov_name] = fov_result

        self.log_message(
            f"Completed {fov_name}: {fov_result['successful_fits']}/{fov_result['n_cells']} cells fitted"
        )

        self.update_results_summary()

    def update_results_summary(self):
        """Update the results summary display."""
        if not self.completed_fovs:
            self.results_summary.setText("No analysis results")
            return

        total_cells = sum(r["n_cells"] for r in self.completed_fovs.values())
        total_successful = sum(
            r["successful_fits"] for r in self.completed_fovs.values()
        )

        success_rate = (total_successful / total_cells * 100) if total_cells > 0 else 0

        summary_text = (
            f"Completed FOVs: {len(self.completed_fovs)}/{self.total_fovs}\\n"
            f"Total cells fitted: {total_successful}/{total_cells}\\n"
            f"Success rate: {success_rate:.1f}%"
        )

        self.results_summary.setText(summary_text)

    def on_export_results(self):
        """Handle export results request."""
        # TODO: Implement results export functionality
        QMessageBox.information(
            self,
            "Export Results",
            "Results export functionality will be implemented in a future update.",
        )

    def log_message(self, message: str):
        """Add a message to the log display."""
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        self.log_text.append(formatted_message)

        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About PyAMA-Qt Analysis",
            "PyAMA-Qt Analysis Application\\n\\n"
            "Advanced trace fitting analysis for fluorescence microscopy data.\\n"
            "Supports parallel processing of multiple FOVs with various\\n"
            "gene expression models.\\n\\n"
            "Part of the PyAMA-Qt suite.",
        )

    def closeEvent(self, event):
        """Handle window close event."""
        if self.is_analysis_running:
            reply = QMessageBox.question(
                self,
                "Analysis Running",
                "Analysis is currently running. Do you want to cancel and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.on_cancel_analysis()
                # Give some time for cleanup
                QTimer.singleShot(1000, lambda: event.accept())
                event.ignore()
            else:
                event.ignore()
        else:
            event.accept()
