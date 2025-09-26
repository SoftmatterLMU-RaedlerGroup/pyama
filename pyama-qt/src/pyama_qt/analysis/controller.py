"""Controller coordinating analysis data loading and fitting."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Any

from PySide6.QtCore import QObject, Signal

from pyama_core.analysis.fitting import fit_trace_data
from pyama_core.io.analysis_csv import discover_csv_files, load_analysis_csv

from pyama_qt.analysis.models import AnalysisDataModel, FittingModel, FittedResultsModel
from pyama_qt.analysis.requests import FittingRequest
from pyama_qt.services import WorkerHandle, start_worker

logger = logging.getLogger(__name__)


class AnalysisController(QObject):
    """Encapsulates the coordination between analysis panels and workers."""

    error_occurred = Signal(str)
    # status_changed = Signal(str)  # Can be removed if panels connect to model signals

    def __init__(self) -> None:
        super().__init__()
        self.data_model = AnalysisDataModel()
        self.fitting_model = FittingModel()
        self.results_model = FittedResultsModel()
        self._worker: WorkerHandle | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_csv(self, path: Path) -> None:
        self.data_model.load_csv(path)

    def start_fitting(self, request: FittingRequest) -> None:
        if self._worker is not None:
            self.error_occurred.emit("A fitting job is already running")
            return

        if self.data_model.raw_data() is None:
            self.error_occurred.emit("Load a CSV file before starting fitting")
            return

        data_path = self.data_model.raw_csv_path()
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
        self.fitting_model.set_is_fitting(True)
        self.fitting_model.set_status_message("Starting batch fitting…")
        self.fitting_model.set_error_message("")

        # self.status_changed.emit("Starting batch fitting…")  # If keeping

    def cancel_fitting(self) -> None:
        if self._worker:
            logger.info("Cancelling analysis fitting worker")
            self._worker.stop()
            self._worker = None
        self.fitting_model.set_is_fitting(False)
        self.fitting_model.set_status_message("Fitting cancelled")
        # self.status_changed.emit("Fitting cancelled")

    def highlight_cell(self, cell_id: str) -> None:
        self.data_model.highlight_cell(cell_id)

    def get_random_cell(self) -> str | None:
        return self.data_model.get_random_cell()

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------
    def _on_worker_progress(self, message: str) -> None:
        self.fitting_model.set_status_message(message)
        # self.status_changed.emit(message)

    def _on_worker_file_processed(self, filename: str, results: pd.DataFrame) -> None:
        logger.info("Processed analysis file %s (%d rows)", filename, len(results))
        self.results_model.set_results(results)
        self.fitting_model.set_status_message(f"Processed {filename}")

    def _on_worker_error(self, message: str) -> None:
        logger.error("Analysis worker error: %s", message)
        self.fitting_model.set_error_message(message)
        self.fitting_model.set_is_fitting(False)
        self.error_occurred.emit(message)

    def _on_worker_finished(self) -> None:
        logger.info("Analysis fitting completed")
        self.fitting_model.set_is_fitting(False)
        self.fitting_model.set_status_message("Fitting complete")

        raw_csv_path = self.data_model.raw_csv_path()
        if raw_csv_path:
            fitted_path = raw_csv_path.parent / f"{raw_csv_path.stem}_fitted.csv"
            if fitted_path.exists():
                try:
                    self.results_model.load_from_csv(fitted_path)
                except Exception as exc:
                    logger.warning("Failed to load fitted results from disk: %s", exc)

    def _on_worker_thread_finished(self) -> None:
        logger.debug("Analysis worker thread finished")
        self._worker = None

    # ------------------------------------------------------------------
    # Internal helpers (removed _update_state and _prepare_all_plot)
    # ------------------------------------------------------------------


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
