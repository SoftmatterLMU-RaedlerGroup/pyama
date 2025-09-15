"""
Main window for PyAMA-Qt processing application.
"""

import logging

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QProgressBar,
)
from PySide6.QtCore import QThread, QObject, Signal
from typing import Any
from pyama_core.io import ND2Metadata

from pyama_core.processing.workflow import run_complete_workflow

from .widgets import Workflow, FileLoader, AssignFovsPanel, MergeSamplesPanel


logger = logging.getLogger(__name__)


class WorkflowWorker(QObject):
    """Worker class for running workflow processing in a separate thread."""

    finished = Signal(bool, str)  # success, message

    def __init__(
        self,
        metadata: ND2Metadata,
        context: dict[str, Any],
        fov_start: int,
        fov_end: int | None,
        batch_size: int,
        n_workers: int,
    ):
        super().__init__()
        self.metadata = metadata
        self.context = context
        self.fov_start = fov_start
        self.fov_end = fov_end
        self.batch_size = batch_size
        self.n_workers = n_workers

    def run_processing(self):
        """Run the workflow processing."""
        try:
            success = run_complete_workflow(
                self.metadata,
                self.context,
                fov_start=self.fov_start,
                fov_end=self.fov_end,
                batch_size=self.batch_size,
                n_workers=self.n_workers,
            )

            if success:
                self.finished.emit(
                    True, f"Results saved to {self.context.get('output_dir')}"
                )
            else:
                self.finished.emit(False, "Workflow failed")

        except Exception as e:
            self.finished.emit(False, f"Workflow error: {str(e)}")


class ProcessingPage(QWidget):
    """Embeddable processing page (QWidget) that contains the full Processing UI and logic."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        logging.basicConfig(level=logging.INFO)

        # Store loaded source info and constructed ND2 metadata
        self._source_info = None
        self._metadata = None

        self._setup_ui()
        logger.info("PyAMA Processing Page loaded")

    def _setup_ui(self):
        # Overall three-column horizontal layout
        main_hlayout = QHBoxLayout(self)
        main_hlayout.setContentsMargins(6, 6, 6, 6)
        main_hlayout.setSpacing(8)

        # Column 1: Processing (existing FileLoader + Workflow stacked)
        processing_col = QWidget()
        processing_vlayout = QVBoxLayout(processing_col)
        processing_vlayout.setContentsMargins(0, 0, 0, 0)
        processing_vlayout.setSpacing(8)

        self.file_loader = FileLoader()
        processing_vlayout.addWidget(self.file_loader)

        self.workflow = Workflow()
        processing_vlayout.addWidget(self.workflow)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate by default
        self.progress_bar.hide()
        processing_vlayout.addWidget(self.progress_bar)

        processing_vlayout.addStretch()

        # Column 2: FOV assignment from merging
        self.fov_assign_panel = AssignFovsPanel(self)

        # Column 3: Merge from merging
        self.merge_panel = MergeSamplesPanel(self)

        # Add the three columns to the main layout with stretch factors
        main_hlayout.addWidget(processing_col, 1)
        main_hlayout.addWidget(self.fov_assign_panel, 1)
        main_hlayout.addWidget(self.merge_panel, 1)

        # Wire signals
        self.file_loader.data_loaded.connect(self.on_data_loaded)
        self.workflow.process_requested.connect(self.start_workflow_processing)

    def on_data_loaded(self, payload):
        # payload is a tuple: (ND2Metadata, context)
        try:
            metadata, context = payload
        except Exception:
            # Backward compatibility: ignore if format differs
            metadata, context = None, None

        if metadata is None:
            logger.error("Invalid data payload emitted by loader")
            return

        self._metadata = metadata
        self._context_from_loader = context or {}

        filepath = str(metadata.nd2_path)
        logger.info(f"ND2 file loaded: {filepath}")

        # Provide loader payload to workflow UI for enabling processing
        self.workflow.set_data_available(
            True,
            {
                "pc_channel": self._context_from_loader.get("channels", {}).get("pc"),
                "fl_channels": self._context_from_loader.get("channels", {}).get(
                    "fl", []
                ),
            },
        )

    def start_workflow_processing(self, payload):
        self.processing_thread = QThread()

        if not self._metadata:
            logger.error("Metadata not initialized; load an ND2 file first")
            return

        # Payload from Workflow widget: {"context": context, "params": params}
        context = payload.get("context", {})
        params = payload.get("params", {})

        # Merge loader-provided context with UI-provided context (output_dir and any overrides)
        merged_context = dict(self._context_from_loader or {})
        try:
            # shallow merge for keys used today
            if context.get("output_dir") is not None:
                merged_context["output_dir"] = context["output_dir"]
            if "channels" in context:
                merged_channels = dict(merged_context.get("channels", {}))
                merged_channels.update(context.get("channels", {}))
                merged_context["channels"] = merged_channels
            if "params" in context and isinstance(context["params"], dict):
                merged_params = dict(merged_context.get("params", {}))
                merged_params.update(context["params"])  # keep extra params
                merged_context["params"] = merged_params
            if "npy_paths" in context and isinstance(context["npy_paths"], dict):
                merged_context["npy_paths"] = context["npy_paths"]
        except Exception:
            pass

        self.workflow_worker = WorkflowWorker(
            self._metadata,
            merged_context,
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
        logger.info("Workflow processing started...")

    def on_processing_finished(self, success, message):
        self.workflow.processing_finished(success, message)
        self.progress_bar.hide()
        if success:
            logger.info("Workflow completed successfully")
        else:
            logger.error(f"Workflow failed: {message}")

    def on_workflow_error(self, error_message):
        self.workflow.processing_error(error_message)
        logger.error(f"Error: {error_message}")

    def update_progress(self, value):
        if value < 0:
            self.progress_bar.setRange(0, 0)  # Indeterminate
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)


class MainWindow(QMainWindow):
    """Main application window for PyAMA-Qt processing tool (standalone wrapper)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyAMA Processing Tool")
        # Wider default size to accommodate three columns
        self.setGeometry(100, 100, 1400, 800)

        # Host the embeddable page
        self.setCentralWidget(ProcessingPage(self))
