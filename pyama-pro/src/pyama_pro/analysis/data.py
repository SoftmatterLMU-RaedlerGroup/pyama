"""Data panel for loading CSV files and plotting traces.

This module provides the DataPanel widget for the analysis tab, which handles:
- Loading analysis CSV files (time series trace data)
- Loading fitted results CSV files with automatic model detection
- Configuring model fitting parameters
- Running background fitting operations
- Visualizing trace data
"""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from pathlib import Path
from typing import Sequence

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
from pyama_core.analysis.models import get_model, get_types, list_models
from pyama_core.io.analysis_csv import discover_csv_files, load_analysis_csv
from pyama_pro.components.mpl_canvas import MplCanvas
from pyama_pro.components.parameter_table import ParameterTable
from pyama_pro.constants import DEFAULT_DIR
from pyama_pro.utils import WorkerHandle, start_worker
from pyama_pro.types.analysis import FittingRequest

logger = logging.getLogger(__name__)

# Type alias for plot data
PlotLine = tuple[Sequence[float], Sequence[float], dict]


# =============================================================================
# MAIN DATA PANEL
# =============================================================================


class DataPanel(QWidget):
    """Left-side panel responsible for loading CSV data and visualisation.

    This panel provides an interface for loading trace data from CSV files,
    visualizing traces, and configuring model fitting parameters. It handles
    background fitting operations and provides signals for communication
    with other components.

    Key features:
    - Load analysis CSV files containing time series trace data
    - Load fitted results CSV files (e.g., `xxx_fitted_maturation.csv`)
    - Automatic model detection: When loading fitted results, the model dropdown
      updates to match the model type from the CSV's `model_type` column
    - Visualize all traces with mean overlay
    - Configure fitting parameters through the parameter table
    - Run fitting operations in background threads
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    raw_data_changed = Signal(object)  # Emitted when raw data is loaded (pd.DataFrame)
    cell_highlighted = Signal(str)  # Emitted when a cell is highlighted (Cell ID)
    fitting_requested = Signal(
        object
    )  # Emitted when fitting is requested (FittingRequest)
    fitting_completed = Signal(object)  # Emitted when fitting completes (pd.DataFrame)
    fitted_results_loaded = Signal(
        object
    )  # Emitted when fitted results are loaded from file (pd.DataFrame)
    fitting_started = Signal()  # Emitted when fitting process starts
    fitting_finished = Signal(
        bool, str
    )  # Emitted when fitting finishes (success, message)
    data_loading_started = Signal()  # Emitted when data loading starts
    data_loading_finished = Signal(
        bool, str
    )  # Emitted when data loading finishes (success, message)
    file_saved = Signal(str, str)  # Emitted when a file is saved (filename, directory)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the data panel.

        Args:
            *args: Positional arguments passed to parent QWidget
            **kwargs: Keyword arguments passed to parent QWidget
        """
        super().__init__(*args, **kwargs)
        self._initialize_state()
        self._build_ui()
        self._connect_signals()
        self._update_parameter_defaults()

    # ------------------------------------------------------------------------
    # STATE INITIALIZATION
    # ------------------------------------------------------------------------
    def _initialize_state(self) -> None:
        """Initialize all internal state variables.

        Sets up all the default values and state tracking variables
        used throughout the data panel, including plot state,
        data state, fitting state, and worker handles.
        """

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
        self._saved_files: list[
            tuple[str, str]
        ] = []  # List of (filename, directory) tuples

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout.

        Creates a vertical layout with two main groups:
        1. Data visualization group with CSV loading and matplotlib canvas
        2. Fitting controls group with model selection and parameter configuration
        """
        layout = QVBoxLayout(self)

        # Data visualization group
        self._data_group = self._build_data_group()
        layout.addWidget(self._data_group)

        # Fitting controls group
        self._fitting_group = self._build_fitting_group()
        layout.addWidget(self._fitting_group)

    def _build_data_group(self) -> QGroupBox:
        """Build the data visualization group.

        Returns:
            QGroupBox containing CSV loading button and matplotlib canvas
        """
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
        """Build the fitting controls group.

        Returns:
            QGroupBox containing model selection, parameter configuration,
            and fitting controls
        """
        group = QGroupBox("Fitting")
        layout = QVBoxLayout(group)

        # Model selection form
        form = QFormLayout()
        self._model_combo = QComboBox()
        self._model_combo.addItems(self._available_model_names())
        form.addRow("Model:", self._model_combo)
        layout.addLayout(form)

        # Parameter panel
        self._param_panel = ParameterTable()
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
        """Connect UI widget signals to handlers.

        Sets up all the signal/slot connections for user interactions,
        including CSV loading, model selection, and fitting operations.
        """
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
        """Return the current raw data DataFrame.

        Returns:
            Current raw data DataFrame or None if no data is loaded
        """
        return self._raw_data

    def raw_csv_path(self) -> Path | None:
        """Return the current CSV file path.

        Returns:
            Path to the current CSV file or None if no file is loaded
        """
        return self._raw_csv_path

    def get_random_cell(self) -> str | None:
        """Get a random cell ID from the current data.

        Returns:
            Random cell ID or None if no data is loaded
        """
        if self._raw_data is None or self._raw_data.empty:
            return None
        return str(np.random.choice(self._raw_data.columns))

    def highlight_cell(self, cell_id: str) -> None:
        """Highlight a specific cell in the plot.

        Args:
            cell_id: ID of the cell to highlight
        """
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
        )
        # Emit signal so other components (like fitting panel) know which cell is visualized.
        self.cell_highlighted.emit(cell_id)

    def clear_all(self) -> None:
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
        """Load CSV data and prepare initial plot.

        Args:
            path: Path to the CSV file to load
        """
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
        """Load fitted results from CSV file.

        Automatically detects the model type from the CSV's `model_type` column
        and updates the model dropdown accordingly. This ensures the UI is
        synchronized with the loaded fitted results.

        Args:
            path: Path to the fitted results CSV file
        """
        logger.info("Loading fitted results from %s", path)
        try:
            df = pd.read_csv(path)

            # Extract model type from CSV and update dropdown
            if "model_type" in df.columns and not df.empty:
                model_type = df["model_type"].iloc[0]
                if pd.notna(model_type) and model_type in self._available_model_names():
                    logger.info("Updating model dropdown to %s", model_type)
                    self._model_combo.blockSignals(True)
                    self._model_combo.setCurrentText(model_type)
                    self._model_combo.blockSignals(False)
                    self._model_type = model_type
                    self._update_parameter_defaults()

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
            styles_data.append(
                {
                    "color": "red",
                    "linewidth": 2,
                    "label": f"Mean of {len(data.columns)} lines",
                }
            )

        self._render_plot_internal(
            lines_data,
            styles_data,
        )

    # ------------------------------------------------------------------------
    # PLOTTING METHODS
    # ------------------------------------------------------------------------
    def clear_plot(self) -> None:
        """Reset the canvas to an empty state."""
        self._canvas.clear()

    def _render_plot_internal(
        self,
        lines_data: list,
        styles_data: list,
        *,
        x_label: str = "Time (hours)",
        y_label: str = "Intensity",
    ) -> None:
        """Internal method to render the plot.

        Args:
            lines_data: List of line data tuples (x, y)
            styles_data: List of style dictionaries
            x_label: X-axis label
            y_label: Y-axis label
        """
        self._canvas.plot_lines(
            lines_data,
            styles_data,
            x_label=x_label,
            y_label=y_label,
        )

    # ------------------------------------------------------------------------
    # UI EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot()
    def _on_load_clicked(self) -> None:
        """Handle CSV file load button click.

        Opens a file dialog to select a CSV file and initiates loading.
        """
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
        """Handle load fitted results button click.

        Opens a file dialog to select a fitted results CSV file and loads it.
        """
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

    def _on_start_clicked(self) -> None:
        """Handle start fitting button click.

        Validates prerequisites and initiates the fitting process.
        """
        logger.debug("UI Click: Start fitting button")
        if self._is_fitting:
            logger.debug("UI Action: Fitting already running, ignoring request")
            self.fitting_finished.emit(False, "A fitting job is already running.")
            return

        if self._raw_csv_path is None:
            logger.debug("UI Action: No CSV loaded, ignoring fitting request")
            self.fitting_finished.emit(
                False, "Load a CSV file before starting fitting."
            )
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

    def _on_model_changed(self, model_type: str) -> None:
        """Handle model type change.

        Args:
            model_type: New model type
        """
        logger.debug("UI Event: Model type changed to - %s", model_type)
        if not model_type:
            return
        self._model_type = model_type
        self._update_parameter_defaults()

    # ------------------------------------------------------------------------
    # PARAMETER MANAGEMENT
    # ------------------------------------------------------------------------
    def _update_parameter_defaults(self) -> None:
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
        """Collect current model parameter values from the panel.

        Returns:
            Dictionary of parameter names to values
        """
        df = self._param_panel.get_values_df()
        return df["value"].to_dict() if df is not None and "value" in df.columns else {}

    def _collect_model_bounds(self) -> dict:
        """Collect current model parameter bounds from the panel.

        Returns:
            Dictionary of parameter names to (min, max) tuples
        """
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
    def _start_fitting_worker(self, request: FittingRequest) -> None:
        """Start background fitting worker with the given request.

        Args:
            request: Fitting request containing model type, parameters, and bounds
        """
        self.fitting_started.emit()

        worker = AnalysisWorker(
            data_folder=self._raw_csv_path,
            model_type=request.model_type,
            model_params=request.model_params,
            model_bounds=request.model_bounds,
        )

        # Connect worker signals
        worker.finished.connect(self._on_worker_finished)

        # Start worker
        handle = start_worker(
            worker,
            start_method="process_data",
            finished_callback=lambda: setattr(self, "_worker_handle", None),
        )
        self._worker = worker  # Store worker reference to access results
        self._worker_handle = handle
        self._set_fitting_active(True)

    # ------------------------------------------------------------------------
    # WORKER CALLBACK HANDLERS
    # ------------------------------------------------------------------------
    def _on_worker_finished(self, success: bool, message: str) -> None:
        """Handle worker completion.

        Args:
            success: Whether the operation succeeded
            message: Completion message
        """
        self._set_fitting_active(False)
        
        if success:
            logger.info("Analysis fitting completed: %s", message)
            # Emit fitting completed signals for processed files
            if self._worker and hasattr(self._worker, '_processed_results'):
                for filename, results_df in self._worker._processed_results:
                    logger.info("Processed analysis file %s (%d rows)", filename, len(results_df))
                    self.fitting_completed.emit(results_df)
            self.fitting_finished.emit(True, message)
        else:
            logger.error("Analysis fitting failed: %s", message)
            self.fitting_finished.emit(False, message)

        # Create completion message with saved CSV files
        if self._saved_files:
            messages = [
                f"{filename} saved to {directory}"
                for filename, directory in self._saved_files
            ]
            completion_message = "; ".join(messages)
        else:
            completion_message = "Fitting completed (no files saved)"

        self.fitting_finished.emit(True, completion_message)
        self._saved_files.clear()  # Reset for next fitting session

    # ------------------------------------------------------------------------
    # UI STATE HELPERS
    # ------------------------------------------------------------------------
    def _set_fitting_active(self, is_active: bool) -> None:
        """Update UI state to reflect fitting activity.

        Args:
            is_active: Whether fitting is currently active
        """
        self._is_fitting = is_active
        if is_active:
            self._progress_bar.setRange(0, 0)  # Indeterminate progress
            self._progress_bar.show()
        else:
            self._progress_bar.hide()
        self._start_button.setEnabled(not is_active)

    def _available_model_names(self) -> Sequence[str]:
        """Get list of available fitting models.

        Returns:
            List of available model names
        """
        try:
            return list_models()
        except Exception:
            return ["trivial", "maturation"]


# =============================================================================
# BACKGROUND FITTING WORKER
# =============================================================================


class AnalysisWorker(QObject):
    """Background worker executing fitting across CSV files.

    This class handles fitting of trace data in a separate thread to prevent
    blocking the UI during long fitting operations. It processes all CSV
    files in the specified directory. Progress updates are logged directly
    using logger.info(). Completion signals are emitted for UI coordination.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    finished = Signal(bool, str)  # Emitted when worker completes (success, message)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(
        self,
        *,
        data_folder: Path,
        model_type: str,
        model_params: dict[str, float],
        model_bounds: dict[str, tuple[float, float]],
    ) -> None:
        """Initialize the analysis worker.

        Args:
            data_folder: Path to the directory containing CSV files
            model_type: Type of model to use for fitting
            model_params: Dictionary of model parameter values
            model_bounds: Dictionary of model parameter bounds
        """
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
        """Execute fitting on all CSV files in the data folder.

        Discovers CSV files in the data folder, loads each file,
        fits the specified model to each trace, and saves the results.
        Progress updates are logged using logger.info(). Completion signals
        are emitted for UI coordination.
        """
        try:
            # Discover CSV files
            trace_files = discover_csv_files(self._data_folder)
            if not trace_files:
                self.finished.emit(False, "No CSV files found for analysis")
                return

            logger.info("Found %d file(s) for fitting", len(trace_files))

            # Process each file
            for id, trace_path in enumerate(trace_files):
                if self._is_cancelled:
                    break

                logger.info("Processing %s (%d/%d)", trace_path.name, id + 1, len(trace_files))

                try:
                    # Load and process the file
                    df = load_analysis_csv(trace_path)
                    cell_columns = df.columns.tolist()
                    total_cells = len(cell_columns)

                    # Fit each cell using actual column names
                    results = []
                    for cell_idx, cell_id in enumerate(cell_columns):
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
                        
                        # Report progress per cell
                        logger.info("Fitting cells: %d/%d", cell_idx, total_cells)

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
                            except Exception as save_exc:
                                logger.warning(
                                    f"Failed to save fitted results: {save_exc}"
                                )

                            # Emit fitting completed signal through DataPanel
                            # Store results to be accessed after finished signal
                            if not hasattr(self, '_processed_results'):
                                self._processed_results = []
                            self._processed_results.append((trace_path.name, results_df))

                except Exception as exc:
                    error_msg = f"Failed to process {trace_path.name}: {exc}"
                    logger.error(error_msg)
                    self.finished.emit(False, error_msg)
                    return

        except Exception as exc:
            logger.exception("Unexpected analysis worker failure")
            self.finished.emit(False, str(exc))
        else:
            # Success - emit finished with success message
            processed_count = len(getattr(self, '_processed_results', []))
            message = f"Fitting completed. Processed {processed_count} file(s)."
            self.finished.emit(True, message)
