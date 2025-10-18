"""Helpers for running QObject workers in dedicated threads."""

# =============================================================================
# IMPORTS
# =============================================================================

from typing import Callable

from PySide6.QtCore import QObject, QThread


# =============================================================================
# WORKER HANDLE
# =============================================================================


class WorkerHandle:
    """Handle for managing a worker running inside a QThread."""

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, thread: QThread, worker: QObject) -> None:
        self._thread = thread
        self._worker = worker

    # ------------------------------------------------------------------------
    # PROPERTIES
    # ------------------------------------------------------------------------
    @property
    def thread(self) -> QThread:
        """Access to the managed thread."""
        return self._thread

    @property
    def worker(self) -> QObject:
        """Access to the managed worker."""
        return self._worker

    # ------------------------------------------------------------------------
    # WORKER CONTROL
    # ------------------------------------------------------------------------
    def cancel(self) -> None:
        """Cancel the worker (alias for stop)."""
        self.stop()

    def stop(self) -> None:
        """Stop the worker and clean up the thread safely."""
        # First try to cancel the worker if it has a cancel method
        if hasattr(self._worker, "cancel"):
            try:
                getattr(self._worker, "cancel")()
            except Exception:  # pragma: no cover - defensive
                pass

        # Disconnect all signals to prevent crashes
        try:
            self._thread.disconnect()
            self._worker.disconnect()
        except Exception:
            pass

        # Request thread interruption
        if self._thread.isRunning():
            self._thread.requestInterruption()
            self._thread.quit()

            # Wait for thread to finish with timeout
            if not self._thread.wait(1000):  # 1 second timeout
                # Force terminate if thread doesn't respond
                self._thread.terminate()
                self._thread.wait(100)  # Brief wait after terminate

        # Clean up objects
        try:
            self._worker.deleteLater()
            self._thread.deleteLater()
        except Exception:
            pass


# =============================================================================
# WORKER MANAGEMENT FUNCTIONS
# =============================================================================


def start_worker(
    worker: QObject,
    start_method: str = "process",
    finished_callback: Callable[[], None] | None = None,
    status_manager=None,
    operation_type=None,
    operation_message: str | None = None,
) -> WorkerHandle:
    """Move ``worker`` to a new ``QThread`` and start ``start_method``."""
    # Start the operation if status manager is provided
    operation_id = None
    if status_manager and operation_type and operation_message:
        operation_id = status_manager.start_operation(operation_type, operation_message)

    # Create a wrapper for the finished callback that also handles the status manager
    def wrapped_finished_callback():
        if finished_callback:
            finished_callback()
        if status_manager and operation_id:
            status_manager.finish_operation(operation_id)

    # Create and configure thread
    thread = QThread()

    # Set thread parent to None to avoid ownership issues
    thread.setParent(None)
    worker.setParent(None)

    # Move worker to thread
    worker.moveToThread(thread)

    # Validate start method exists
    if not hasattr(worker, start_method):
        raise AttributeError(f"Worker {worker!r} has no method '{start_method}'")

    # Connect thread started signal to worker method
    start_callable = getattr(worker, start_method)
    thread.started.connect(start_callable)  # type: ignore[arg-type]

    # Connect worker finished signal to thread quit
    if hasattr(worker, "finished"):
        worker.finished.connect(thread.quit)  # type: ignore[attr-defined]

    # Set up cleanup connections
    thread.finished.connect(lambda: thread.deleteLater())
    thread.finished.connect(lambda: worker.deleteLater())

    # Connect optional finished callback
    if wrapped_finished_callback is not None:
        thread.finished.connect(wrapped_finished_callback)

    # Start the thread
    thread.start()
    return WorkerHandle(thread, worker)
