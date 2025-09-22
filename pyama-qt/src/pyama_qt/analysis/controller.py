"""Controller coordinating analysis data loading and fitting."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama_core.analysis.fitting import fit_trace_data
from pyama_core.io.analysis_csv import discover_csv_files, load_analysis_csv

from pyama_qt.analysis.state import AnalysisState, FittingRequest
from pyama_qt.services import WorkerHandle, start_worker

logger = logging.getLogger(__name__)


class AnalysisController(QObject):
    """Encapsulates the coordination between analysis panels and workers."""

    state_changed = Signal(object)
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._state = AnalysisState()
        self._worker: WorkerHandle | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def current_state(self) -> AnalysisState:
        return self._state

    def load_csv(self, path: Path) -> None:
        logger.info("Loading analysis CSV from %s", path)
        try:
            data = load_analysis_csv(path)
        except Exception as exc:
            logger.exception("Failed to load analysis CSV")
            self._update_state(error_message=str(exc))
            self.error_occurred.emit(str(exc))
            return

        self._update_state(
            raw_csv_path=path,
            raw_data=data,
            status_message=f"Loaded {len(data.columns)} cells from {path.name}",
            error_message="",
            selected_cell=None,
        )
        self._auto_load_fitted_results(path)

    def start_fitting(self, request: FittingRequest) -> None:
        if self._worker is not None:
            self.error_occurred.emit("A fitting job is already running")
            return

        if self._state.raw_csv_path is None:
            self.error_occurred.emit("Load a CSV file before starting fitting")
            return

        data_path = self._state.raw_csv_path
        worker = _AnalysisWorker(
            data_folder=data_path,
            request=request,
        )
        worker.progress_updated.connect(self._on_worker_progress)
        worker.file_processed.connect(self._on_worker_file_processed)
        worker.error_occurred.connect(self._on_worker_error)
        worker.finished.connect(self._on_worker_finished)

        handle = start_worker(
            worker,
            start_method="process_data",
            finished_callback=self._on_worker_thread_finished,
        )
        self._worker = handle
        self._update_state(is_fitting=True, status_message="Starting batch fitting…", error_message="")

    def cancel_fitting(self) -> None:
        if self._worker:
            logger.info("Cancelling analysis fitting worker")
            self._worker.stop()
            self._worker = None
        self._update_state(is_fitting=False, status_message="Fitting cancelled")

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------
    def _on_worker_progress(self, message: str) -> None:
        self._update_state(status_message=message)
        self.status_changed.emit(message)

    def _on_worker_file_processed(self, filename: str, results: pd.DataFrame) -> None:
        logger.info("Processed analysis file %s (%d rows)", filename, len(results))
        self._update_state(fitted_results=results, status_message=f"Processed {filename}")

    def _on_worker_error(self, message: str) -> None:
        logger.error("Analysis worker error: %s", message)
        self._update_state(error_message=message, is_fitting=False)
        self.error_occurred.emit(message)

    def _on_worker_finished(self) -> None:
        logger.info("Analysis fitting completed")
        self._update_state(is_fitting=False, status_message="Fitting complete")

        if self._state.raw_csv_path:
            fitted_path = self._state.raw_csv_path.parent / f"{self._state.raw_csv_path.stem}_fitted.csv"
            if fitted_path.exists():
                try:
                    results = pd.read_csv(fitted_path)
                    self._update_state(fitted_results=results, fitted_csv_path=fitted_path)
                except Exception as exc:
                    logger.warning("Failed to load fitted results from disk: %s", exc)

    def _on_worker_thread_finished(self) -> None:
        logger.debug("Analysis worker thread finished")
        self._worker = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _auto_load_fitted_results(self, csv_path: Path) -> None:
        fitted_path = csv_path.parent / f"{csv_path.stem}_fitted.csv"
        if fitted_path.exists():
            try:
                results = pd.read_csv(fitted_path)
                self._update_state(
                    fitted_results=results,
                    fitted_csv_path=fitted_path,
                    status_message=f"Loaded fitted results ({len(results)} rows)",
                )
            except Exception as exc:
                logger.warning("Failed to load fitted results: %s", exc)

    def _update_state(self, **updates) -> None:
        for key, value in updates.items():
            setattr(self._state, key, value)
        self.state_changed.emit(self._state)


class _AnalysisWorker(QObject):
    """Background worker executing fitting across CSV files."""

    progress_updated = Signal(str)
    file_processed = Signal(str, object)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, *, data_folder: Path, request: FittingRequest) -> None:
        super().__init__()
        self._data_folder = data_folder
        self._request = request
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def process_data(self) -> None:
        try:
            trace_files = discover_csv_files(self._data_folder)
            if not trace_files:
                self.error_occurred.emit("No CSV files found for analysis")
                return

            self.progress_updated.emit(f"Found {len(trace_files)} file(s) for fitting")

            for idx, trace_path in enumerate(trace_files):
                if self._is_cancelled:
                    self.progress_updated.emit("Fitting cancelled")
                    break

                self.progress_updated.emit(
                    f"Processing {trace_path.name} ({idx + 1}/{len(trace_files)})"
                )

                try:
                    df = load_analysis_csv(trace_path)
                except Exception as exc:
                    self.error_occurred.emit(f"Failed to load {trace_path.name}: {exc}")
                    continue

                n_cells = df.shape[1]
                results = []

                for cell_idx in range(n_cells):
                    if self._is_cancelled:
                        break

                    try:
                        fit_result = fit_trace_data(
                            df,
                            self._request.model_type,
                            cell_idx,
                            progress_callback=None,
                            user_params=self._request.model_params,
                            user_bounds=self._request.model_bounds,
                        )
                        record = {
                            "cell_id": cell_idx,
                            "model_type": self._request.model_type,
                            "success": fit_result.success,
                            "r_squared": fit_result.r_squared,
                        }
                        record.update(fit_result.fitted_params)
                        results.append(record)
                    except Exception as exc:
                        logger.error("Error fitting cell %s: %s", cell_idx, exc)
                        continue

                if results:
                    results_df = pd.DataFrame(results)
                    output_path = trace_path.parent / f"{trace_path.stem}_fitted.csv"
                    results_df.to_csv(output_path, index=False)
                    self.file_processed.emit(trace_path.name, results_df)

            self.finished.emit()
        except Exception as exc:  # pragma: no cover - top-level safeguard
            logger.exception("Critical error in analysis worker")
            self.error_occurred.emit(str(exc))
            self.finished.emit()
