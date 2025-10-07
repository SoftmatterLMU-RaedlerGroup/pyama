"""Controller coordinating analysis data loading and fitting."""

import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama_core.analysis.fitting import fit_trace_data, get_trace
from pyama_core.analysis.models import get_model, get_types, list_models
from pyama_core.io.analysis_csv import discover_csv_files, load_analysis_csv

from pyama_qt.models.analysis import AnalysisDataModel, FittingModel, FittedResultsModel
from pyama_qt.models.analysis_requests import FittingRequest
from pyama_qt.services import WorkerHandle, start_worker

from pyama_qt.views.analysis.page import AnalysisPage

logger = logging.getLogger(__name__)


class AnalysisController(QObject):
    """Controller implementing the strict PySide6 MVC rules for the analysis tab."""

    def __init__(self, view: AnalysisPage) -> None:
        super().__init__()
        self._view = view
        self._data_model = AnalysisDataModel()
        self._fitting_model = FittingModel()
        self._results_model = FittedResultsModel()
        self._worker: WorkerHandle | None = None

        self._current_plot_title: str = ""
        self._current_plot_data: Sequence[tuple] | None = None
        self._current_cell: str | None = None
        self._selected_parameter: str | None = None
        self._default_params: dict[str, float] = {}
        self._default_bounds: dict[str, tuple[float, float]] = {}
        self._parameter_names: list[str] = []

        self._connect_view_signals()
        self._connect_model_signals()
        self._initialise_defaults()

    # ------------------------------------------------------------------
    # Signal wiring helpers
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        data_panel = self._view.data_panel
        data_panel.csv_selected.connect(self._on_csv_selected)

        fitting_panel = self._view.fitting_panel
        fitting_panel.set_available_models(self._available_model_names())
        fitting_panel.fit_requested.connect(self._on_fit_requested)
        fitting_panel.visualize_requested.connect(self._on_visualize_requested)
        fitting_panel.shuffle_requested.connect(self._on_shuffle_requested)
        fitting_panel.model_changed.connect(self._on_model_changed)
        fitting_panel.cell_visualized.connect(self._on_cell_visualized)

        results_panel = self._view.results_panel
        results_panel.parameter_selected.connect(self._on_parameter_selected)
        results_panel.filter_toggled.connect(self._on_filter_toggled)
        results_panel.save_requested.connect(self._on_save_requested)

    def _connect_model_signals(self) -> None:
        self._data_model.rawDataChanged.connect(self._handle_raw_data_changed)
        self._data_model.plotDataChanged.connect(self._handle_plot_data_changed)
        self._data_model.plotTitleChanged.connect(self._handle_plot_title_changed)

        self._fitting_model.isFittingChanged.connect(
            self._view.fitting_panel.set_fitting_active
        )
        self._fitting_model.statusMessageChanged.connect(
            self._view.status_bar.showMessage
        )

        self._results_model.resultsReset.connect(self._handle_results_reset)

    def _initialise_defaults(self) -> None:
        self._on_model_changed(self._fitting_model.model_type())

    # ------------------------------------------------------------------
    # View → Controller handlers
    # ------------------------------------------------------------------
    def _on_csv_selected(self, path: Path) -> None:
        self._load_csv(path)

    def _on_fit_requested(
        self,
        model_type: str,
        params: dict,
        bounds: dict,
        manual: bool,
    ) -> None:
        if self._data_model.raw_data() is None:
            self._view.status_bar.showMessage("Load a CSV file before starting fitting")
            return

        model_params = params if manual and params else self._default_params
        model_bounds = bounds if manual and bounds else self._default_bounds

        request = FittingRequest(
            model_type=model_type,
            model_params=model_params,
            model_bounds=model_bounds,
        )
        self._fitting_model.set_model_params(model_params)
        self._fitting_model.set_model_bounds(model_bounds)
        self._start_fitting(request)

    def _on_visualize_requested(self, cell_name: str) -> None:
        if not cell_name:
            return
        raw = self._data_model.raw_data()
        if raw is None or cell_name not in raw.columns:
            self._view.status_bar.showMessage(f"Cell '{cell_name}' not found")
            return

        cell_index = list(raw.columns).index(cell_name)
        time_data, intensity_data = get_trace(raw, cell_index)

        lines: list[tuple[np.ndarray, np.ndarray]] = [(time_data, intensity_data)]
        styles = [
            {
                "plot_style": "scatter",
                "color": "blue",
                "alpha": 0.6,
                "s": 20,
                "label": f"{cell_name} (data)",
            }
        ]

        self._append_fitted_curve(cell_index, time_data, lines, styles)

        self._view.fitting_panel.show_cell_visualization(
            cell_name=cell_name,
            lines=lines,
            styles=styles,
            title=f"Quality Control - {cell_name}",
            x_label="Time (hours)",
            y_label="Intensity",
        )
        self._current_cell = cell_name

    def _on_shuffle_requested(self) -> None:
        cell_name = self._data_model.get_random_cell()
        if not cell_name:
            return
        self._view.fitting_panel.set_cell_candidate(cell_name)
        self._on_visualize_requested(cell_name)

    def _on_model_changed(self, model_type: str) -> None:
        if not model_type:
            return
        self._fitting_model.set_model_type(model_type)
        self._update_parameter_defaults(model_type)

    def _on_cell_visualized(self, cell_id: str) -> None:
        self._data_model.highlight_cell(cell_id)

    def _on_parameter_selected(self, param_name: str) -> None:
        self._selected_parameter = param_name
        self._update_histogram()

    def _on_filter_toggled(self, _checked: bool) -> None:
        self._update_histogram()

    def _on_save_requested(self, folder: Path) -> None:
        df = self._results_model.results()
        if df is None or df.empty or not self._parameter_names:
            return

        current_param = self._selected_parameter
        for param_name in self._parameter_names:
            series = self._histogram_series(df, param_name)
            if series is None or series.empty:
                continue
            self._view.results_panel.render_histogram(
                param_name=param_name,
                values=series.tolist(),
            )
            output = folder / f"{param_name}.png"
            self._view.results_panel.export_histogram(output)

        if current_param:
            self._selected_parameter = current_param
            self._update_histogram()

    # ------------------------------------------------------------------
    # Model → Controller handlers
    # ------------------------------------------------------------------
    def _handle_raw_data_changed(self, _: pd.DataFrame) -> None:
        self._current_cell = None
        self._view.fitting_panel.clear_qc_view()

    def _handle_plot_data_changed(self, plot_data: Sequence[tuple] | None) -> None:
        self._current_plot_data = plot_data
        self._view.data_panel.render_plot(
            plot_data,
            title=self._current_plot_title,
            x_label="Time (hours)",
            y_label="Intensity",
        )

    def _handle_plot_title_changed(self, title: str) -> None:
        self._current_plot_title = title
        self._view.data_panel.render_plot(
            self._current_plot_data,
            title=title,
            x_label="Time (hours)",
            y_label="Intensity",
        )

    def _handle_results_reset(self) -> None:
        df = self._results_model.results()
        if df is None or df.empty:
            self._parameter_names = []
            self._selected_parameter = None
            self._view.results_panel.clear()
            return

        self._update_quality_plot(df)
        parameter_names = self._discover_numeric_parameters(df)
        self._parameter_names = parameter_names

        current = self._selected_parameter
        if current not in parameter_names:
            current = parameter_names[0] if parameter_names else None
        self._selected_parameter = current

        self._view.results_panel.set_parameter_options(
            parameter_names,
            current=current,
        )
        self._update_histogram()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_csv(self, path: Path) -> None:
        self._data_model.load_csv(path)

        fitted_path = path.parent / f"{path.stem}_fitted.csv"
        if fitted_path.exists():
            try:
                self._results_model.load_from_csv(fitted_path)
                logger.info("Loaded existing fitted results from %s", fitted_path)
            except Exception as exc:
                logger.warning(
                    "Failed to load fitted results from %s: %s", fitted_path, exc
                )
        else:
            self._results_model.clear_results()
            logger.info("No fitted results found for %s", path)

        self._view.status_bar.showMessage(f"Loaded {path.name}")

    def _start_fitting(self, request: FittingRequest) -> None:
        if self._worker is not None:
            self._view.status_bar.showMessage("A fitting job is already running")
            return

        data_path = self._data_model.raw_csv_path()
        if data_path is None:
            self._view.status_bar.showMessage("CSV path not available for fitting")
            return

        worker = _AnalysisWorker(data_folder=data_path, request=request)
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
        self._fitting_model.set_is_fitting(True)
        self._fitting_model.set_status_message("Starting batch fitting…")
        self._fitting_model.set_error_message("")

    def _available_model_names(self) -> Sequence[str]:
        try:
            return list_models()
        except Exception:
            return ["trivial", "maturation"]

    def _update_parameter_defaults(self, model_type: str) -> None:
        try:
            model = get_model(model_type)
            types = get_types(model_type)
            user_params = types["UserParams"]
            rows = []
            defaults: dict[str, float] = {}
            bounds: dict[str, tuple[float, float]] = {}
            for name in user_params.__annotations__.keys():
                default_val = getattr(model.DEFAULTS, name)
                min_val, max_val = getattr(model.BOUNDS, name)
                defaults[name] = float(default_val)
                bounds[name] = (float(min_val), float(max_val))
                rows.append(
                    {
                        "name": name,
                        "value": default_val,
                        "min": min_val,
                        "max": max_val,
                    }
                )
            df = pd.DataFrame(rows).set_index("name") if rows else pd.DataFrame()
        except Exception as exc:
            logger.warning("Failed to prepare parameter defaults: %s", exc)
            df = pd.DataFrame()
            defaults = {}
            bounds = {}

        self._default_params = defaults
        self._default_bounds = bounds
        self._view.fitting_panel.set_parameter_defaults(df)
        self._fitting_model.set_model_params(defaults)
        self._fitting_model.set_model_bounds(bounds)

    def _append_fitted_curve(
        self,
        cell_index: int,
        time_data: np.ndarray,
        lines: list[tuple[np.ndarray, np.ndarray]],
        styles: list[dict],
    ) -> None:
        results = self._results_model.results()
        if results is None or results.empty:
            return

        cell_fit = results[results["cell_id"] == cell_index]
        if cell_fit.empty:
            return

        first_fit = cell_fit.iloc[0]
        success_val = first_fit.get("success")
        if not (
            success_val in [True, "True", "true", 1, "1"]
            or (isinstance(success_val, str) and str(success_val).lower() == "true")
        ):
            return

        model_type = str(first_fit.get("model_type", "")).lower()
        try:
            model = get_model(model_type)
            types = get_types(model_type)
            user_params = types["UserParams"]
            params_cls = types["Params"]
            param_names = list(user_params.__annotations__.keys())
            params_dict = {}
            for name in param_names:
                if name in cell_fit.columns and pd.notna(first_fit[name]):
                    params_dict[name] = float(first_fit[name])
            if len(params_dict) != len(param_names):
                return
            all_param_names = list(params_cls.__annotations__.keys())
            default_dict = {p: getattr(model.DEFAULTS, p) for p in all_param_names}
            default_dict.update(params_dict)
            params_obj = params_cls(**default_dict)
            t_smooth = np.linspace(time_data.min(), time_data.max(), 200)
            y_fit = model.eval(t_smooth, params_obj)
            r_squared = float(first_fit.get("r_squared", 0))
            lines.append((t_smooth, y_fit))
            styles.append(
                {
                    "plot_style": "line",
                    "color": "red",
                    "linewidth": 2,
                    "label": f"Fit (R²={r_squared:.3f})",
                }
            )
        except Exception as exc:
            logger.warning(
                "Failed to add fitted curve for cell %s: %s", cell_index, exc
            )

    def _update_histogram(self) -> None:
        df = self._results_model.results()
        if df is None or df.empty or not self._selected_parameter:
            self._view.results_panel.render_histogram(
                param_name=self._selected_parameter or "",
                values=[],
            )
            return

        series = self._histogram_series(df, self._selected_parameter)
        if series is None or series.empty:
            self._view.results_panel.render_histogram(
                param_name=self._selected_parameter,
                values=[],
            )
            return

        self._view.results_panel.render_histogram(
            param_name=self._selected_parameter,
            values=series.tolist(),
        )

    def _histogram_series(self, df: pd.DataFrame, param_name: str) -> pd.Series | None:
        data = pd.to_numeric(df.get(param_name), errors="coerce").dropna()
        if data.empty:
            return None

        if "r_squared" in df.columns and self._view.results_panel.is_filter_enabled():
            mask = pd.to_numeric(df["r_squared"], errors="coerce") > 0.9
            data = pd.to_numeric(df.loc[mask, param_name], errors="coerce").dropna()
            if data.empty:
                return None
        return data

    def _update_quality_plot(self, df: pd.DataFrame) -> None:
        r_squared = pd.to_numeric(df.get("r_squared"), errors="coerce").dropna()
        if r_squared.empty:
            self._view.results_panel.render_quality_plot(
                lines=[],
                styles=[],
                title="Fitting Quality",
                x_label="Cell Index",
                y_label="R²",
            )
            return

        colors = [
            "green" if r2 > 0.9 else "orange" if r2 > 0.7 else "red" for r2 in r_squared
        ]
        lines = [(list(range(len(r_squared))), r_squared.values)]
        styles = [
            {
                "plot_style": "scatter",
                "color": colors,
                "alpha": 0.6,
                "s": 20,
            }
        ]

        good_pct = (r_squared > 0.9).mean() * 100
        fair_pct = ((r_squared > 0.7) & (r_squared <= 0.9)).mean() * 100
        poor_pct = (r_squared <= 0.7).mean() * 100

        legend_text = (
            f"Good (R²>0.9): {good_pct:.1f}%\n"
            f"Fair (0.7<R²≤0.9): {fair_pct:.1f}%\n"
            f"Poor (R²≤0.7): {poor_pct:.1f}%"
        )
        self._view.results_panel.render_quality_plot(
            lines=lines,
            styles=styles,
            title="Fitting Quality",
            x_label="Cell Index",
            y_label="R²",
            legend_text=legend_text,
        )

    def _discover_numeric_parameters(self, df: pd.DataFrame) -> list[str]:
        metadata_cols = {
            "fov",
            "file",
            "cell_id",
            "model_type",
            "success",
            "residual_sum_squares",
            "message",
            "n_function_calls",
            "chisq",
            "std",
            "r_squared",
        }
        numeric_cols: list[str] = []
        for col in df.columns:
            if col in metadata_cols:
                continue
            numeric = pd.to_numeric(df[col], errors="coerce")
            if numeric.notna().any():
                numeric_cols.append(col)
        return numeric_cols

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------
    def _on_worker_progress(self, message: str) -> None:
        self._fitting_model.set_status_message(message)

    def _on_worker_file_processed(self, filename: str, results: pd.DataFrame) -> None:
        logger.info("Processed analysis file %s (%d rows)", filename, len(results))
        self._results_model.set_results(results)
        self._fitting_model.set_status_message(f"Processed {filename}")

    def _on_worker_error(self, message: str) -> None:
        logger.error("Analysis worker error: %s", message)
        self._fitting_model.set_error_message(message)
        self._fitting_model.set_is_fitting(False)
        self._view.status_bar.showMessage(message)

    def _on_worker_finished(self) -> None:
        logger.info("Analysis fitting completed")
        self._fitting_model.set_is_fitting(False)
        self._fitting_model.set_status_message("Fitting complete")

        raw_csv_path = self._data_model.raw_csv_path()
        if raw_csv_path:
            fitted_path = raw_csv_path.parent / f"{raw_csv_path.stem}_fitted.csv"
            if fitted_path.exists():
                try:
                    self._results_model.load_from_csv(fitted_path)
                except Exception as exc:
                    logger.warning("Failed to load fitted results from disk: %s", exc)

    def _on_worker_thread_finished(self) -> None:
        logger.info("Analysis worker thread finished")
        self._worker = None


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

                def progress_callback(cell_id):
                    if cell_id % 30 == 0 or cell_id == n_cells - 1:
                        logger.info(f"Fitting cell: {cell_id + 1}/{n_cells}")

                for cell_idx in range(n_cells):
                    if self._is_cancelled:
                        break

                    try:
                        fit_result = fit_trace_data(
                            df,
                            self._request.model_type,
                            cell_idx,
                            progress_callback=progress_callback,
                            bounds=self._request.model_bounds,
                            initial_params=self._request.model_params,
                        )
                        results.append(fit_result)
                    except Exception as exc:
                        logger.warning(
                            "Failed to fit cell %s in %s: %s",
                            cell_idx,
                            trace_path.name,
                            exc,
                        )
                        continue

                if results:
                    results_df = pd.DataFrame(results)
                    results_df["cell_id"] = results_df.get(
                        "cell_id", range(len(results))
                    )
                    self.file_processed.emit(trace_path.name, results_df)

        except Exception as exc:
            logger.exception("Unexpected analysis worker failure")
            self.error_occurred.emit(str(exc))
        finally:
            self.finished.emit()
