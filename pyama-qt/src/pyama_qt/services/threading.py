"""Helpers for running QObject workers in dedicated threads."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread


class WorkerHandle:
    """Handle for managing a worker running inside a QThread."""

    def __init__(self, thread: QThread, worker: QObject) -> None:
        self._thread = thread
        self._worker = worker

    @property
    def thread(self) -> QThread:
        return self._thread

    @property
    def worker(self) -> QObject:
        return self._worker

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


def start_worker(
    worker: QObject,
    start_method: str = "process",
    finished_callback: Callable[[], None] | None = None,
) -> WorkerHandle:
    """Move ``worker`` to a new ``QThread`` and start ``start_method``."""
    thread = QThread()

    # Set thread parent to None to avoid ownership issues
    thread.setParent(None)
    worker.setParent(None)

    worker.moveToThread(thread)

    if not hasattr(worker, start_method):
        raise AttributeError(f"Worker {worker!r} has no method '{start_method}'")

    start_callable = getattr(worker, start_method)
    thread.started.connect(start_callable)  # type: ignore[arg-type]

    # If worker has a 'finished' signal, connect it to quit the thread
    if hasattr(worker, "finished"):
        worker.finished.connect(thread.quit)  # type: ignore[attr-defined]

    # Clean up connections when thread finishes
    thread.finished.connect(lambda: thread.deleteLater())
    thread.finished.connect(lambda: worker.deleteLater())

    if finished_callback is not None:
        thread.finished.connect(finished_callback)

    thread.start()
    return WorkerHandle(thread, worker)
