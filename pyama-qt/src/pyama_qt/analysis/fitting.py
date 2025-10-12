"""Fitting controls and quality inspection panel."""

import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from pyama_core.analysis.fitting import fit_trace_data, get_trace
from pyama_core.analysis.models import get_model, get_types, list_models
from pyama_core.io.analysis_csv import discover_csv_files, load_analysis_csv
from pyama_qt.models.analysis_requests import FittingRequest
from pyama_qt.services import WorkerHandle, start_worker

from ..base import BasePanel
from ..components.mpl_canvas import MplCanvas
from ..components.parameter_panel import ParameterPanel

logger = logging.getLogger(__name__)


class FittingPanel(BasePanel):
    """Middle panel for model selection, fitting, and QC plots."""

    # Signals for other components
    fittingCompleted = Signal(object)  # pd.DataFrame
    statusMessage = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # --- State from DataPanel ---
        self._raw_data: pd.DataFrame | None = None
        self._raw_csv_path: Path | None = None

        # --- State from FittingModel ---
        self._is_fitting: bool = False
        self._model_type: str = "trivial"
        self._model_params: dict[str, float] = {}
        self._model_bounds: dict[str, tuple[float, float]] = {}
        self._default_params: dict[str, float] = {}
        self._default_bounds: dict[str, tuple[float, float]] = {}

        # --- State for Visualization ---
        self._current_qc_cell: str | None = None
        self._fitted_results: pd.DataFrame | None = None

        # --- Worker ---
        self._worker: WorkerHandle | None = None

    def build(self) -> None:
        layout = QVBoxLayout(self)
        self._fitting_group = self._build_fitting_group()
        self._qc_group = self._build_qc_group()
        layout.addWidget(self._fitting_group, 1)
        layout.addWidget(self._qc_group, 1)
        self._update_parameter_defaults()

    def bind(self) -> None:
        self._start_button.clicked.connect(self._on_start_clicked)
        self._visualize_button.clicked.connect(self._on_visualize_clicked)
        self._shuffle_button.clicked.connect(self.shuffle_requested.emit)
        self._model_combo.currentTextChanged.connect(self._on_model_changed)

    # --- Public Slots for connection to other components ---
    def on_raw_data_changed(self, df: pd.DataFrame):
        self._raw_data = df
        self.clear_qc_view()
        # When new data is loaded, clear previous fit results
        self._fitted_results = None

    def on_raw_csv_path_changed(self, path: Path):
        self._raw_csv_path = path

    def on_shuffle_requested(self, get_random_cell_func):
        cell_name = get_random_cell_func()
        if cell_name:
            self._cell_input.setText(cell_name)
            self._visualize_cell(cell_name)

    def on_fitted_results_changed(self, df: pd.DataFrame):
        self._fitted_results = df
        # If a cell is currently visualized, refresh the plot to show the fit
        if self._current_qc_cell:
            self._visualize_cell(self._current_qc_cell)

    # --- Internal Logic (from Controller) ---
    def _on_start_clicked(self):
        if self._is_fitting:
            self.statusMessage.emit("A fitting job is already running.")
            return

        if self._raw_csv_path is None:
            self.statusMessage.emit("Load a CSV file before starting fitting.")
            return

        manual = self._param_panel.use_manual_params.isChecked()
        model_params = self._collect_model_params() if manual else self._default_params
        model_bounds = self._collect_model_bounds() if manual else self._default_bounds

        request = FittingRequest(
            model_type=self._model_type,
            model_params=model_params,
            model_bounds=model_bounds,
        )

        self._start_fitting_worker(request)

    def _on_visualize_clicked(self):
        cell_name = self._cell_input.text().strip()
        if cell_name:
            self._visualize_cell(cell_name)

    def _visualize_cell(self, cell_name: str):
        if self._raw_data is None or cell_name not in self._raw_data.columns:
            self.statusMessage.emit(f"Cell '{cell_name}' not found.")
            return

        cell_index = list(self._raw_data.columns).index(cell_name)
        time_data, intensity_data = get_trace(self._raw_data, cell_index)

        lines = [(time_data, intensity_data)]
        styles = [{"plot_style": "scatter", "color": "blue", "alpha": 0.6, "s": 20, "label": f"{cell_name} (data)"}]

        self._append_fitted_curve(cell_index, time_data, lines, styles)

        self._qc_canvas.plot_lines(
            lines,
            styles,
            title=f"Quality Control - {cell_name}",
            x_label="Time (hours)",
            y_label="Intensity",
        )
        self._current_qc_cell = cell_name

    def _on_model_changed(self, model_type: str):
        if not model_type:
            return
        self._model_type = model_type
        self._update_parameter_defaults()

    def _update_parameter_defaults(self):
        try:
            model = get_model(self._model_type)
            types = get_types(self._model_type)
            user_params = types["UserParams"]
            rows = []
            defaults: dict[str, float] = {}
            bounds: dict[str, tuple[float, float]] = {}
            for name in user_params.__annotations__.keys():
                default_val = getattr(model.DEFAULTS, name)
                min_val, max_val = getattr(model.BOUNDS, name)
                defaults[name] = float(default_val)
                bounds[name] = (float(min_val), float(max_val))
                rows.append({"name": name, "value": default_val, "min": min_val, "max": max_val})
            df = pd.DataFrame(rows).set_index("name") if rows else pd.DataFrame()
        except Exception as exc:
            logger.warning("Failed to prepare parameter defaults: %s", exc)
            df = pd.DataFrame()
            defaults = {}
            bounds = {}

        self._default_params = defaults
        self._default_bounds = bounds
        self._param_panel.set_parameters_df(df)

    def _start_fitting_worker(self, request: FittingRequest):
        worker = _AnalysisWorker(data_folder=self._raw_csv_path, request=request)
        worker.progress_updated.connect(self._on_worker_progress)
        worker.file_processed.connect(self._on_worker_file_processed)
        worker.error_occurred.connect(self._on_worker_error)
        worker.finished.connect(self._on_worker_finished)

        handle = start_worker(
            worker,
            start_method="process_data",
            finished_callback=lambda: setattr(self, "_worker", None),
        )
        self._worker = handle
        self._set_fitting_active(True)
        self.statusMessage.emit("Starting batch fitting…")

    # --- Worker Callbacks ---
    def _on_worker_progress(self, message: str):
        self.statusMessage.emit(message)

    def _on_worker_file_processed(self, filename: str, results: pd.DataFrame):
        logger.info("Processed analysis file %s (%d rows)", filename, len(results))
        self.fittingCompleted.emit(results)
        self.statusMessage.emit(f"Processed {filename}")

    def _on_worker_error(self, message: str):
        logger.error("Analysis worker error: %s", message)
        self.statusMessage.emit(message)
        self._set_fitting_active(False)

    def _on_worker_finished(self):
        logger.info("Analysis fitting completed")
        self._set_fitting_active(False)
        self.statusMessage.emit("Fitting complete")

    # --- UI and State Helpers ---
    def _set_fitting_active(self, is_active: bool):
        self._is_fitting = is_active
        if is_active:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.show()
        else:
            self._progress_bar.hide()
        self._start_button.setEnabled(not is_active)

    def clear_qc_view(self):
        self._qc_canvas.clear()
        self._current_qc_cell = None
        self._cell_input.clear()

    def _append_fitted_curve(self, cell_index, time_data, lines, styles):
        if self._fitted_results is None or self._fitted_results.empty:
            return

        cell_fit = self._fitted_results[self._fitted_results["cell_id"] == cell_index]
        if cell_fit.empty:
            return

        first_fit = cell_fit.iloc[0]
        if not first_fit.get("success", False):
            return

        try:
            model = get_model(self._model_type)
            types = get_types(self._model_type)
            params_cls = types["Params"]
            param_names = list(types["UserParams"].__annotations__.keys())

            params_dict = {name: float(first_fit[name]) for name in param_names if name in first_fit and pd.notna(first_fit[name])}
            if len(params_dict) != len(param_names): return

            all_param_names = list(params_cls.__annotations__.keys())
            default_dict = {p: getattr(model.DEFAULTS, p) for p in all_param_names}
            default_dict.update(params_dict)

            params_obj = params_cls(**default_dict)
            t_smooth = np.linspace(time_data.min(), time_data.max(), 200)
            y_fit = model.eval(t_smooth, params_obj)
            r_squared = float(first_fit.get("r_squared", 0))

            lines.append((t_smooth, y_fit))
            styles.append({"plot_style": "line", "color": "red", "linewidth": 2, "label": f"Fit (R²={r_squared:.3f})"})
        except Exception as exc:
            logger.warning("Failed to add fitted curve for cell %s: %s", cell_index, exc)

    # --- UI Building ---
    def _build_fitting_group(self) -> QGroupBox:
        group = QGroupBox("Fitting")
        layout = QVBoxLayout(group)
        form = QFormLayout()
        self._model_combo = QComboBox()
        self._model_combo.addItems(self._available_model_names())
        form.addRow("Model:", self._model_combo)
        layout.addLayout(form)
        self._param_panel = ParameterPanel()
        layout.addWidget(self._param_panel)
        self._start_button = QPushButton("Start Fitting")
        layout.addWidget(self._start_button)
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)
        return group

    def _build_qc_group(self) -> QGroupBox:
        group = QGroupBox("Quality Check")
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self._cell_input = QLineEdit()
        self._cell_input.setPlaceholderText("Enter cell ID to visualize")
        row.addWidget(self._cell_input)
        self._visualize_button = QPushButton("Visualize")
        row.addWidget(self._visualize_button)
        self._shuffle_button = QPushButton("Shuffle")
        row.addWidget(self._shuffle_button)
        layout.addLayout(row)
        self._qc_canvas = MplCanvas(self, width=5, height=3)
        layout.addWidget(self._qc_canvas)
        return group

    def _available_model_names(self) -> Sequence[str]:
        try:
            return list_models()
        except Exception:
            return ["trivial", "maturation"]

    def _collect_model_params(self) -> dict:
        df = self._param_panel.get_values_df()
        return df["value"].to_dict() if df is not None and "value" in df.columns else {}

    def _collect_model_bounds(self) -> dict:
        df = self._param_panel.get_values_df()
        if df is None or "min" not in df.columns or "max" not in df.columns:
            return {}
        return {name: (float(row["min"]), float(row["max"])) for name, row in df.iterrows() if pd.notna(row["min"]) and pd.notna(row["max"])}


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
                if self._is_cancelled: break
                self.progress_updated.emit(f"Processing {trace_path.name} ({idx + 1}/{len(trace_files)})")
                try:
                    df = load_analysis_csv(trace_path)
                    n_cells = df.shape[1]
                    results = [
                        fit_trace_data(
                            df, self._request.model_type, i,
                            bounds=self._request.model_bounds,
                            initial_params=self._request.model_params
                        )
                        for i in range(n_cells) if not self._is_cancelled
                    ]
                    if results:
                        results_df = pd.DataFrame([r for r in results if r])
                        if not results_df.empty:
                            results_df["cell_id"] = results_df.get("cell_id", range(len(results_df)))
                            self.file_processed.emit(trace_path.name, results_df)
                except Exception as exc:
                    self.error_occurred.emit(f"Failed to process {trace_path.name}: {exc}")
        except Exception as exc:
            logger.exception("Unexpected analysis worker failure")
            self.error_occurred.emit(str(exc))
        finally:
            self.finished.emit()