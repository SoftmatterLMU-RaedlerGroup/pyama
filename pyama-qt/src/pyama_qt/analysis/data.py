"""Data panel for loading CSV files and plotting traces."""

# =============================================================================
# IMPORTS
# =============================================================================

import hashlib
import logging
from pyama_qt.types.analysis import FittingRequest
from pathlib import Path
from typing import Dict, Sequence

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal, Slot
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
from pyama_qt.constants import DEFAULT_DIR
from pyama_qt.services import WorkerHandle, start_worker
from pyama_core.analysis.models import get_model, get_types, list_models

from pyama_qt.components.mpl_canvas import MplCanvas
from pyama_qt.components.parameter_panel import ParameterPanel

logger = logging.getLogger(__name__)


# Type alias for plot data
PlotLine = tuple[Sequence[float], Sequence[float], dict]


# =============================================================================
# MAIN DATA PANEL
# =============================================================================


class DataPanel(QWidget):
    """Left-side panel responsible for loading CSV data and visualisation."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    raw_data_changed = Signal(object)  # pd.DataFrame - when raw data is loaded
    cell_highlighted = Signal(str)  # Cell ID - when a cell is highlighted
    fitting_requested = Signal(object)  # FittingRequest - when fitting is requested
    fitting_completed = Signal(object)  # pd.DataFrame - when fitting completes
    fitted_results_loaded = Signal(
        object
    )  # pd.DataFrame - when fitted results are loaded from file
    fitting_started = Signal()  # When fitting process starts
    data_loading_started = Signal()  # When data loading starts
    data_loading_finished = Signal(
        bool, str
    )  # When data loading finishes (success, message)
    file_saved = Signal(str, str)  # filename, directory - when a file is saved

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initialize_state()
        self._build_ui()
        self._connect_signals()
        self._update_parameter_defaults()

    # ------------------------------------------------------------------------
    # STATE INITIALIZATION
    # ------------------------------------------------------------------------
    def _initialize_state(self) -> None:
        """Initialize all internal state variables."""
        # Plot state
        self._last_plot_hash: str | None = None
        self._current_title = ""

        # Data state (from AnalysisDataModel)
        self._raw_data: pd.DataFrame | None = None
        self._raw_csv_path: Path | None = None
        self._selected_cell: str | None = None

        # Fitting state (from FittingModel)
        self._is_fitting: bool = False
        self._model_type: str = "trivial"
        self._model_params: dict[str, float] = {}
        self._model_bounds: dict[str, tuple[float, float]] = {}
        self._default_params: dict[str, float] = {}
        self._default_bounds: dict[str, tuple[float, float]] = {}

        # Worker handle
        self._worker: WorkerHandle | None = None

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout."""
        layout = QVBoxLayout(self)

        # Data visualization group
        self._data_group = self._build_data_group()
        layout.addWidget(self._data_group)

        # Fitting controls group
        self._fitting_group = self._build_fitting_group()
        layout.addWidget(self._fitting_group)

    def _build_data_group(self) -> QGroupBox:
        """Build the data visualization group."""
        group = QGroupBox("Data Visualization")
        group_layout = QVBoxLayout(group)

        # Load CSV button
        self._load_button = QPushButton("Load CSV")
        group_layout.addWidget(self._load_button)

        # Matplotlib canvas for plotting
        self._canvas = MplCanvas(self)
        group_layout.addWidget(self._canvas)
        self._canvas.clear()

        return group

    def _build_fitting_group(self) -> QGroupBox:
        """Build the fitting controls group."""
        group = QGroupBox("Fitting")
        layout = QVBoxLayout(group)

        # Model selection form
        form = QFormLayout()
        self._model_combo = QComboBox()
        self._model_combo.addItems(self._available_model_names())
        form.addRow("Model:", self._model_combo)
        layout.addLayout(form)

        # Parameter panel
        self._param_panel = ParameterPanel()
        layout.addWidget(self._param_panel)

        # Load fitted results button
        self._load_fitted_results_button = QPushButton("Load Fitted Results")
        layout.addWidget(self._load_fitted_results_button)

        # Start fitting button
        self._start_button = QPushButton("Start Fitting")
        layout.addWidget(self._start_button)

        # Progress bar (initially hidden)
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        return group

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers."""
        self._load_button.clicked.connect(self._on_load_clicked)
        self._load_fitted_results_button.clicked.connect(
            self._on_load_fitted_results_clicked
        )
        self._start_button.clicked.connect(self._on_start_clicked)
        self._model_combo.currentTextChanged.connect(self._on_model_changed)

    # ------------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------------
    def raw_data(self) -> pd.DataFrame | None:
        """Return the current raw data DataFrame."""
        return self._raw_data

    def raw_csv_path(self) -> Path | None:
        """Return the current CSV file path."""
        return self._raw_csv_path

    def get_random_cell(self) -> str | None:
        """Get a random cell ID from the current data."""
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

        # Plot all other cells in gray
        for other_id in data.columns:
            if other_id != cell_id:
                lines_data.append((time_values, data[other_id].values))
                styles_data.append({"color": "gray", "alpha": 0.1, "linewidth": 0.5})

        # Highlight selected cell in blue
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
        self.cell_highlighted.emit(cell_id)

    def clear_all(self):
        """Clear data, plot, and state."""
        self._raw_data = None
        self._raw_csv_path = None
        self._selected_cell = None
        self.clear_plot()
        self.raw_data_changed.emit(pd.DataFrame())

    # ------------------------------------------------------------------------
    # DATA LOADING
    # ------------------------------------------------------------------------
    def _load_csv(self, path: Path) -> None:
        """Load CSV data and prepare initial plot."""
        logger.info("Loading analysis CSV from %s", path)
        filename = path.name
        self.data_loading_started.emit()

        try:
            df = load_analysis_csv(path)
            self._raw_data = df
            self._raw_csv_path = path

            self._prepare_all_plot()

            # Emit signal after data is loaded and plot is prepared
            self.raw_data_changed.emit(df)

            self.data_loading_finished.emit(True, f"Successfully loaded {filename}")

        except Exception as e:
            logger.exception("Failed to load analysis CSV")
            self.data_loading_finished.emit(False, f"Failed to load {filename}: {e}")
            # Maybe show an error message to the user? For now, just log.
            self.clear_all()

    def _load_fitted_results(self, path: Path) -> None:
        """Load fitted results from CSV file."""
        logger.info("Loading fitted results from %s", path)
        try:
            df = pd.read_csv(path)
            self.fitted_results_loaded.emit(df)
            logger.info("Loaded existing fitted results from %s", path)
        except Exception as e:
            logger.warning("Failed to load fitted results from %s: %s", path, e)

    def _prepare_all_plot(self) -> None:
        """Prepare plot data for all traces."""
        if self._raw_data is None:
            self.clear_plot()
            return

        data = self._raw_data
        time_values = data.index.values
        lines_data = []
        styles_data = []

        # Plot all cells in gray
        for col in data.columns:
            lines_data.append((time_values, data[col].values))
            styles_data.append({"color": "gray", "alpha": 0.2, "linewidth": 0.5})

        # Plot mean line in red
        if not data.empty:
            mean = data.mean(axis=1).values
            lines_data.append((time_values, mean))
            styles_data.append({"color": "red", "linewidth": 2, "label": "Mean"})

        self._render_plot_internal(
            lines_data,
            styles_data,
            title=f"All Sequences ({len(data.columns)} cells)",
        )

    # ------------------------------------------------------------------------
    # PLOTTING METHODS
    # ------------------------------------------------------------------------
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
        """Internal method to render the plot with caching."""
        # Create cache key to avoid unnecessary redraws
        cached_payload = (tuple(map(repr, lines_data)), tuple(map(repr, styles_data)))
        new_hash = hashlib.md5(repr(cached_payload).encode()).hexdigest()

        # Skip redraw if data is unchanged
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

    # ------------------------------------------------------------------------
    # UI EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot()
    def _on_load_clicked(self) -> None:
        """Handle CSV file load button click."""
        logger.debug("UI Click: Load CSV file button")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            str(DEFAULT_DIR),  # QFileDialog needs a string path
            "CSV Files (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            logger.debug("UI Action: Loading CSV file - %s", file_path)
            self._load_csv(Path(file_path))

    @Slot()
    def _on_load_fitted_results_clicked(self) -> None:
        """Handle load fitted results button click."""
        logger.debug("UI Click: Load fitted results button")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Fitted Results CSV",
            str(DEFAULT_DIR),
            "CSV Files (*.csv);;Fitted Results (*_fitted_*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            logger.debug("UI Action: Loading fitted results from - %s", file_path)
            self._load_fitted_results(Path(file_path))

    def _on_start_clicked(self):
        """Handle start fitting button click."""
        logger.debug("UI Click: Start fitting button")
        if self._is_fitting:
            logger.debug("UI Action: Fitting already running, ignoring request")
            self.status_message.emit("A fitting job is already running.")
            return

        if self._raw_csv_path is None:
            logger.debug("UI Action: No CSV loaded, ignoring fitting request")
            self.status_message.emit("Load a CSV file before starting fitting.")
            return

        # Collect fitting parameters
        manual = self._param_panel.is_manual_mode()
        model_params = self._collect_model_params() if manual else self._default_params
        model_bounds = self._collect_model_bounds() if manual else self._default_bounds

        request = FittingRequest(
            model_type=self._model_type,
            model_params=model_params,
            model_bounds=model_bounds,
        )

        logger.debug(
            "UI Event: Starting fitting with model %s, params=%s, bounds=%s",
            self._model_type,
            model_params,
            model_bounds,
        )
        self._start_fitting_worker(request)

    def _on_model_changed(self, model_type: str):
        """Handle model type change."""
        logger.debug("UI Event: Model type changed to - %s", model_type)
        if not model_type:
            return
        self._model_type = model_type
        self._update_parameter_defaults()

    # ------------------------------------------------------------------------
    # PARAMETER MANAGEMENT
    # ------------------------------------------------------------------------
    def _update_parameter_defaults(self):
        """Update parameter panel with defaults for current model type (one-way initialization)."""
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
        # One-way binding: set initial values only, don't maintain sync from model
        self._param_panel.set_parameters_df(df)

    def _collect_model_params(self) -> dict:
        """Collect current model parameter values from the panel."""
        df = self._param_panel.get_values_df()
        return df["value"].to_dict() if df is not None and "value" in df.columns else {}

    def _collect_model_bounds(self) -> dict:
        """Collect current model parameter bounds from the panel."""
        df = self._param_panel.get_values_df()
        if df is None or "min" not in df.columns or "max" not in df.columns:
            return {}
        return {
            name: (float(row["min"]), float(row["max"]))
            for name, row in df.iterrows()
            if pd.notna(row["min"]) and pd.notna(row["max"])
        }

    # ------------------------------------------------------------------------
    # FITTING WORKER MANAGEMENT
    # ------------------------------------------------------------------------
    def _start_fitting_worker(self, request: FittingRequest):
        """Start background fitting worker with the given request."""
        self.fitting_started.emit()

        worker = AnalysisWorker(
            data_folder=self._raw_csv_path,
            model_type=request.model_type,
            model_params=request.model_params,
            model_bounds=request.model_bounds,
        )

        # Connect worker signals
        worker.progress_updated.connect(self._on_worker_progress)
        worker.file_processed.connect(self._on_worker_file_processed)
        worker.error_occurred.connect(self._on_worker_error)
        worker.finished.connect(self._on_worker_finished)

        # Start worker
        handle = start_worker(
            worker,
            start_method="process_data",
            finished_callback=lambda: setattr(self, "_worker", None),
        )
        self._worker = handle
        self._set_fitting_active(True)
        self.status_message.emit("Starting batch fitting…")

    # ------------------------------------------------------------------------
    # WORKER CALLBACK HANDLERS
    # ------------------------------------------------------------------------
    def _on_worker_progress(self, message: str):
        """Handle worker progress updates."""
        self.status_message.emit(message)

    def _on_worker_file_processed(self, filename: str, results: pd.DataFrame):
        """Handle successful processing of a single file."""
        logger.info("Processed analysis file %s (%d rows)", filename, len(results))
        self.fitting_completed.emit(results)
        self.status_message.emit(f"Processed {filename}")

    def _on_worker_error(self, message: str):
        """Handle worker errors."""
        logger.error("Analysis worker error: %s", message)
        self.status_message.emit(message)
        self._set_fitting_active(False)

    def _on_worker_finished(self):
        """Handle worker completion."""
        logger.info("Analysis fitting completed")
        self._set_fitting_active(False)
        self.status_message.emit("Fitting complete")

    # ------------------------------------------------------------------------
    # UI STATE HELPERS
    # ------------------------------------------------------------------------
    def _set_fitting_active(self, is_active: bool):
        """Update UI state to reflect fitting activity."""
        self._is_fitting = is_active
        if is_active:
            self._progress_bar.setRange(0, 0)  # Indeterminate progress
            self._progress_bar.show()
        else:
            self._progress_bar.hide()
        self._start_button.setEnabled(not is_active)

    def _available_model_names(self) -> Sequence[str]:
        """Get list of available fitting models."""
        try:
            return list_models()
        except Exception:
            return ["trivial", "maturation"]


# =============================================================================
# BACKGROUND FITTING WORKER
# =============================================================================


class AnalysisWorker(QObject):
    """Background worker executing fitting across CSV files."""

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    progress_updated = Signal(str)  # Progress messages
    file_processed = Signal(str, object)  # Filename and results DataFrame
    finished = Signal()  # Worker completion
    error_occurred = Signal(str)  # Error messages

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
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

    # ------------------------------------------------------------------------
    # CONTROL METHODS
    # ------------------------------------------------------------------------
    def cancel(self) -> None:
        """Cancel the fitting process."""
        self._is_cancelled = True

    # ------------------------------------------------------------------------
    # WORK EXECUTION
    # ------------------------------------------------------------------------
    def process_data(self) -> None:
        """Execute fitting on all CSV files in the data folder."""
        try:
            # Discover CSV files
            trace_files = discover_csv_files(self._data_folder)
            if not trace_files:
                self.error_occurred.emit("No CSV files found for analysis")
                return

            self.progress_updated.emit(f"Found {len(trace_files)} file(s) for fitting")

            # Process each file
            for id, trace_path in enumerate(trace_files):
                if self._is_cancelled:
                    break

                self.progress_updated.emit(
                    f"Processing {trace_path.name} ({id + 1}/{len(trace_files)})"
                )

                try:
                    # Load and process the file
                    df = load_analysis_csv(trace_path)
                    cell_columns = df.columns.tolist()

                    # Fit each cell using actual column names
                    results = []
                    for cell_id in cell_columns:
                        if self._is_cancelled:
                            break
                        result = fit_trace_data(
                            df,
                            self._model_type,
                            cell_id,
                            user_bounds=self._model_bounds,
                            user_params=self._model_params,
                        )
                        results.append((cell_id, result))

                    # Process results
                    if results:
                        # Flatten fitted_params into separate columns
                        flattened_results = []
                        for cell_id, r in results:
                            if r:
                                row = {
                                    "cell_id": cell_id,
                                    "model_type": self._model_type,
                                    "success": r.success,
                                    "r_squared": r.r_squared,
                                }
                                # Flatten the fitted_params dictionary
                                row.update(r.fitted_params)
                                flattened_results.append(row)

                        if flattened_results:
                            results_df = pd.DataFrame(flattened_results)

                            # Save fitted results to CSV file
                            try:
                                fitted_csv_path = trace_path.with_name(
                                    f"{trace_path.stem}_fitted_{self._model_type}.csv"
                                )
                                results_df.to_csv(fitted_csv_path, index=False)
                                logger.info(
                                    f"Saved fitted results to {fitted_csv_path}"
                                )
                                # Emit signal for status message
                                self.file_saved.emit(fitted_csv_path.name, str(fitted_csv_path.parent))
                            except Exception as save_exc:
                                logger.warning(
                                    f"Failed to save fitted results: {save_exc}"
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
