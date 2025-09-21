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
        if hasattr(self._worker, "cancel"):
            try:
                getattr(self._worker, "cancel")()
            except Exception:  # pragma: no cover - defensive
                pass
        self._thread.requestInterruption()
        self._thread.quit()
        self._thread.wait()


def start_worker(
    worker: QObject,
    start_method: str = "process",
    finished_callback: Callable[[], None] | None = None,
) -> WorkerHandle:
    """Move ``worker`` to a new ``QThread`` and start ``start_method``."""
    thread = QThread()
    worker.moveToThread(thread)

    if not hasattr(worker, start_method):
        raise AttributeError(f"Worker {worker!r} has no method '{start_method}'")

    start_callable = getattr(worker, start_method)
    thread.started.connect(start_callable)  # type: ignore[arg-type]

    thread.finished.connect(thread.deleteLater)
    worker.destroyed.connect(thread.quit)

    if finished_callback is not None:
        thread.finished.connect(finished_callback)

    thread.start()
    return WorkerHandle(thread, worker)
