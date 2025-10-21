"""Threading utilities for pyama-air GUI."""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal

logger = logging.getLogger(__name__)


# =============================================================================
# BACKGROUND WORKER
# =============================================================================


class BackgroundWorker(QObject):
    """Background worker for running tasks in separate threads."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    started = Signal()
    finished = Signal(bool, str)  # success, message
    progress = Signal(int)  # progress percentage
    status_message = Signal(str)  # status message

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._task: Callable[[], tuple[bool, str]] | None = None
        self._thread: QThread | None = None

    # ------------------------------------------------------------------------
    # TASK MANAGEMENT
    # ------------------------------------------------------------------------
    def set_task(self, task: Callable[[], tuple[bool, str]]) -> None:
        """Set the task to run in background."""
        self._task = task

    def start_task(self) -> None:
        """Start the background task."""
        if not self._task:
            logger.error("No task set for background worker")
            self.finished.emit(False, "No task set")
            return

        # Create and start thread
        self._thread = QThread()
        self.moveToThread(self._thread)

        # Connect thread signals
        self._thread.started.connect(self._run_task)
        self._thread.finished.connect(self._cleanup_thread)

        # Start thread
        self._thread.start()

    def cancel_task(self) -> None:
        """Cancel the background task."""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()

    # ------------------------------------------------------------------------
    # TASK EXECUTION
    # ------------------------------------------------------------------------
    def _run_task(self) -> None:
        """Run the background task."""
        try:
            logger.info("Background task started")
            self.started.emit()

            if self._task:
                success, message = self._task()
                self.finished.emit(success, message)
            else:
                self.finished.emit(False, "No task available")

        except Exception as exc:
            logger.error("Background task failed: %s", exc)
            self.finished.emit(False, f"Task failed: {exc}")

    def _cleanup_thread(self) -> None:
        """Clean up the thread after completion."""
        if self._thread:
            self._thread.deleteLater()
            self._thread = None
        logger.info("Background task thread cleaned up")
