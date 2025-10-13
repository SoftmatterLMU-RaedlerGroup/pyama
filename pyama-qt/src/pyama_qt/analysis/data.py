"""Data panel for loading CSV files and plotting traces."""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Sequence

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_core.analysis.fitting import fit_trace_data
from pyama_core.io.analysis_csv import discover_csv_files, load_analysis_csv
from pyama_qt.config import DEFAULT_DIR
from pyama_qt.services import WorkerHandle, start_worker
from pyama_core.analysis.models import get_model, get_types, list_models

from ..components.mpl_canvas import MplCanvas
from ..components.parameter_panel import ParameterPanel


@dataclass(slots=True)
class FittingRequest:
    """Parameters for triggering a fitting job."""

    model_type: str
    model_params: Dict[str, float] = field(default_factory=dict)
    model_bounds: Dict[str, tuple[float, float]] = field(default_factory=dict)


PlotLine = tuple[Sequence[float], Sequence[float], dict]

logger = logging.getLogger(__name__)


class DataPanel(QWidget):
    """Left-side panel responsible for loading CSV data and visualisation."""

    # Signals for other components to connect to
    rawDataChanged = Signal(object)  # pd.DataFrame
    rawCsvPathChanged = Signal(object)  # Path
    # This signal will be used by the fitting panel to get a random cell
    cellHighlighted = Signal(str)
    fittingRequested = Signal(object)  # FittingRequest
    fittingCompleted = Signal(object)  # pd.DataFrame
    statusMessage = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_plot_hash: str | None = None
        self.build()
        self.bind()
        self._current_title = ""

        # --- State from AnalysisDataModel ---
        self._raw_data: pd.DataFrame | None = None
        self._raw_csv_path: Path | None = None
        self._selected_cell: str | None = None

        # --- State from FittingModel ---
        self._is_fitting: bool = False
        self._model_type: str = "trivial"
        self._model_params: dict[str, float] = {}
        self._model_bounds: dict[str, tuple[float, float]] = {}
        self._default_params: dict[str, float] = {}
        self._default_bounds: dict[str, tuple[float, float]] = {}

        # --- Worker ---
        self._worker: WorkerHandle | None = None

        self._update_parameter_defaults()

    def build(self) -> None:
        layout = QVBoxLayout(self)

        # Data visualization group
        self._data_group = self._build_data_group()
        layout.addWidget(self._data_group)

        # Fitting controls group
        self._fitting_group = self._build_fitting_group()
        layout.addWidget(self._fitting_group)

    def _build_data_group(self) -> QGroupBox:
        group = QGroupBox("Data Visualization")
        group_layout = QVBoxLayout(group)

        self._load_button = QPushButton("Load CSV")
        group_layout.addWidget(self._load_button)

        self._canvas = MplCanvas(self)
        group_layout.addWidget(self._canvas)
        self._canvas.clear()

        return group

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

    def bind(self) -> None:
        self._load_button.clicked.connect(self._on_load_clicked)
        self._start_button.clicked.connect(self._on_start_clicked)
        self._model_combo.currentTextChanged.connect(self._on_model_changed)

    # --- Public API for other components ---
    def raw_data(self) -> pd.DataFrame | None:
        return self._raw_data

    def raw_csv_path(self) -> Path | None:
        return self._raw_csv_path

    def get_random_cell(self) -> str | None:
        """Get a random cell ID."""
        if self._raw_data is None or self._raw_data.empty:
            return None
        return str(np.random.choice(self._raw_data.columns))

    def highlight_cell(self, cell_id: str) -> None:
        """Highlight a specific cell in the plot."""
        if self._raw_data is None or cell_id not in self._raw_data.columns:
            return
        self._selected_cell = cell_id

        data = self._raw_data
        time_values = data.index.values

        lines_data = []
        styles_data = []

        for other_id in data.columns:
            if other_id != cell_id:
                lines_data.append((time_values, data[other_id].values))
                styles_data.append({"color": "gray", "alpha": 0.1, "linewidth": 0.5})

        lines_data.append((time_values, data[cell_id].values))
        styles_data.append(
            {"color": "blue", "linewidth": 2, "label": f"Cell {cell_id}"}
        )

        self._render_plot_internal(
            lines_data,
            styles_data,
            title=f"Cell {cell_id} Highlighted",
        )
        # Emit signal so other components (like fitting panel) know which cell is visualized.
        self.cellHighlighted.emit(cell_id)

    def clear_all(self):
        """Clear data, plot, and state."""
        self._raw_data = None
        self._raw_csv_path = None
        self._selected_cell = None
        self.clear_plot()
        self.rawDataChanged.emit(pd.DataFrame())
        self.rawCsvPathChanged.emit(Path())

    # --- Internal Logic (previously in Model/Controller) ---
    def _load_csv(self, path: Path) -> None:
        """Load CSV data and prepare initial plot."""
        logger.info("Loading analysis CSV from %s", path)
        try:
            df = load_analysis_csv(path)
            self._raw_data = df
            self._raw_csv_path = path

            self._prepare_all_plot()

            # Emit signals after data is loaded and plot is prepared
            self.rawDataChanged.emit(df)
            self.rawCsvPathChanged.emit(path)

        except Exception:
            logger.exception("Failed to load analysis CSV")
            # Maybe show an error message to the user? For now, just log.
            self.clear_all()

    def _prepare_all_plot(self) -> None:
        """Prepare plot data for all traces."""
        if self._raw_data is None:
            self.clear_plot()
            return

        data = self._raw_data
        time_values = data.index.values
        lines_data = []
        styles_data = []

        for col in data.columns:
            lines_data.append((time_values, data[col].values))
            styles_data.append({"color": "gray", "alpha": 0.2, "linewidth": 0.5})

        # Mean line
        if not data.empty:
            mean = data.mean(axis=1).values
            lines_data.append((time_values, mean))
            styles_data.append({"color": "red", "linewidth": 2, "label": "Mean"})

        self._render_plot_internal(
            lines_data,
            styles_data,
            title=f"All Sequences ({len(data.columns)} cells)",
        )

    # --- Plotting Methods (from original Panel) ---
    def clear_plot(self) -> None:
        """Reset the canvas to an empty state."""
        self._canvas.clear()
        self._last_plot_hash = None

    def _render_plot_internal(
        self,
        lines_data: list,
        styles_data: list,
        *,
        title: str = "",
        x_label: str = "Time (hours)",
        y_label: str = "Intensity",
    ) -> None:
        """Internal method to render the plot."""
        cached_payload = (tuple(map(repr, lines_data)), tuple(map(repr, styles_data)))
        new_hash = hashlib.md5(repr(cached_payload).encode()).hexdigest()

        if new_hash == self._last_plot_hash and title == self._current_title:
            return

        self._canvas.plot_lines(
            lines_data,
            styles_data,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
        self._last_plot_hash = new_hash
        self._current_title = title

    # --- UI Event Handlers (from original Panel) ---
    def _on_load_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            str(DEFAULT_DIR),  # QFileDialog needs a string path
            "CSV Files (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._load_csv(Path(file_path))

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
                rows.append(
                    {"name": name, "value": default_val, "min": min_val, "max": max_val}
                )
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
        worker = AnalysisWorker(
            data_folder=self._raw_csv_path,
            model_type=request.model_type,
            model_params=request.model_params,
            model_bounds=request.model_bounds,
        )
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
        return {
            name: (float(row["min"]), float(row["max"]))
            for name, row in df.iterrows()
            if pd.notna(row["min"]) and pd.notna(row["max"])
        }


class AnalysisWorker(QObject):
    """Background worker executing fitting across CSV files."""

    progress_updated = Signal(str)
    file_processed = Signal(str, object)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        *,
        data_folder: Path,
        model_type: str,
        model_params: Dict[str, float],
        model_bounds: Dict[str, tuple[float, float]],
    ) -> None:
        super().__init__()
        self._data_folder = data_folder
        self._model_type = model_type
        self._model_params = model_params
        self._model_bounds = model_bounds
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
                    break
                self.progress_updated.emit(
                    f"Processing {trace_path.name} ({idx + 1}/{len(trace_files)})"
                )
                try:
                    df = load_analysis_csv(trace_path)
                    n_cells = df.shape[1]
                    results = [
                        fit_trace_data(
                            df,
                            self._model_type,
                            i,
                            user_bounds=self._model_bounds,
                            user_params=self._model_params,
                        )
                        for i in range(n_cells)
                        if not self._is_cancelled
                    ]
                    if results:
                        results_df = pd.DataFrame([r for r in results if r])
                        if not results_df.empty:
                            results_df["cell_id"] = results_df.get(
                                "cell_id", range(len(results_df))
                            )
                            self.file_processed.emit(trace_path.name, results_df)
                except Exception as exc:
                    self.error_occurred.emit(
                        f"Failed to process {trace_path.name}: {exc}"
                    )
        except Exception as exc:
            logger.exception("Unexpected analysis worker failure")
            self.error_occurred.emit(str(exc))
        finally:
            self.finished.emit()
