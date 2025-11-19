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

from pyama_core.analysis.fitting_service import FittingService
from pyama_core.analysis.models import get_model, list_models
from pyama_core.io.analysis_csv import load_analysis_csv
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
        # Initialize parameter defaults for the default model
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
        # Get first available model as default (will be set in _build_ui)
        self._model_type: str = ""
        self._model_params: dict[str, float] = {}
        self._model_bounds: dict[str, tuple[float, float]] = {}
        self._default_params: dict[str, float] = {}
        self._default_bounds: dict[str, tuple[float, float]] = {}

        # Worker handle
        self._worker: WorkerHandle | None = None
        self._saved_files: list[
            tuple[str, str]
        ] = []  # List of (filename, directory) tuples (unused; kept for compatibility)

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
        model_names = self._available_model_names()
        self._model_combo.addItems(model_names)
        # Set default selection to first available model
        if model_names:
            self._model_combo.setCurrentIndex(0)
            self._model_type = model_names[0]
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

        saved_csv_path: Path | None = None

        try:
            df = load_analysis_csv(path)
            self._raw_data = df
            self._raw_csv_path = path
            try:
                cell_count = len(df.index.unique())
            except Exception:
                cell_count = 0
            logger.info(
                "Loaded analysis CSV %s (%d rows, %d cells)", path, len(df), cell_count
            )

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
        self.data_loading_started.emit()
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
            logger.info(
                "Loaded existing fitted results from %s (%d rows)", path, len(df)
            )
            self.data_loading_finished.emit(
                True, f"Loaded fitted results from {path.name}"
            )
        except Exception as e:
            logger.warning("Failed to load fitted results from %s: %s", path, e)
            self.data_loading_finished.emit(
                False, f"Failed to load fitted results: {path.name}"
            )

    def _prepare_all_plot(self) -> None:
        """Prepare plot data for all traces."""
        if self._raw_data is None:
            self.clear_plot()
            return

        data = self._raw_data
        lines_data = []
        styles_data = []

        # Get unique (fov, cell) combinations from MultiIndex
        cell_ids = data.index.unique().tolist()

        # Collect all values for mean calculation
        all_values = []

        # Plot all cells in gray
        for fov, cell in cell_ids:
            cell_data = data.loc[(fov, cell)]
            time_values = cell_data["time"].values
            trace_values = cell_data["value"].values
            lines_data.append((time_values, trace_values))
            styles_data.append({"color": "gray", "alpha": 0.2, "linewidth": 0.5})
            all_values.append(trace_values)

        # Plot mean line in red
        if all_values:
            # Compute mean across all traces (assuming same time points)
            mean_values = np.mean(all_values, axis=0)
            # Use time from first cell
            first_cell = cell_ids[0]
            time_values = data.loc[first_cell]["time"].values
            lines_data.append((time_values, mean_values))
            styles_data.append(
                {
                    "color": "red",
                    "linewidth": 2,
                    "label": f"Mean of {len(cell_ids)} traces",
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
        logger.debug("UI Click: Load CSV file button (start_dir=%s)", DEFAULT_DIR)
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
        logger.debug(
            "UI Click: Load fitted results button (start_dir=%s)", DEFAULT_DIR
        )
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
        logger.debug(
            "UI Click: Start fitting button (csv_loaded=%s, model=%s, manual_mode=%s)",
            bool(self._raw_csv_path),
            self._model_type,
            self._param_panel.is_manual_mode(),
        )
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
        if not self._model_type:
            return
        try:
            model = get_model(self._model_type)
            
            # Extract both fixed and fit parameters for the table
            defaults: dict[str, float] = {}
            bounds: dict[str, tuple[float, float]] = {}
            
            # Build dict structure: {param_name: {field: value, ...}, ...}
            params_dict = {}
            
            # Add fixed parameters (no bounds, so min/max are None)
            for param_name, fixed_param in model.DEFAULT_FIXED.items():
                defaults[param_name] = fixed_param.value
                params_dict[param_name] = {
                    "name": fixed_param.name,
                    "value": fixed_param.value,
                    "min": None,  # Fixed parameters don't have bounds
                    "max": None,
                }
            
            # Add fit parameters (with bounds)
            for param_name, fit_param in model.DEFAULT_FIT.items():
                defaults[param_name] = fit_param.value
                bounds[param_name] = (fit_param.lb, fit_param.ub)
                params_dict[param_name] = {
                    "name": fit_param.name,
                    "value": fit_param.value,
                    "min": fit_param.lb,
                    "max": fit_param.ub,
                }
        except Exception as exc:
            logger.warning("Failed to prepare parameter defaults: %s", exc)
            params_dict = {}
            defaults = {}
            bounds = {}

        self._default_params = defaults
        self._default_bounds = bounds
        # One-way binding: set initial values only, don't maintain sync from model
        self._param_panel.set_parameters(params_dict)

    def _collect_model_params(self) -> dict:
        """Collect current model parameter values from the panel.

        Returns:
            Dictionary of parameter names to values (includes both fixed and fit parameters)
        """
        values_dict = self._param_panel.get_values()
        if values_dict is None:
            return {}
        # Extract 'value' field from each parameter's fields dict
        return {
            param_name: fields.get("value")
            for param_name, fields in values_dict.items()
            if "value" in fields and fields.get("value") is not None
        }

    def _collect_model_bounds(self) -> dict:
        """Collect current model parameter bounds from the panel.

        Returns:
            Dictionary of parameter names to (min, max) tuples
        """
        values_dict = self._param_panel.get_values()
        if values_dict is None:
            return {}
        return {
            param_name: (float(fields["min"]), float(fields["max"]))
            for param_name, fields in values_dict.items()
            if "min" in fields and "max" in fields
            and fields["min"] is not None and fields["max"] is not None
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

        worker = AnalysisFittingWorker(
            csv_file=self._raw_csv_path,
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
            logger.info(
                "Analysis fitting completed (model=%s): %s",
                self._model_type,
                message,
            )
            # Emit fitting completed signals for processed files
            if self._worker and hasattr(self._worker, '_processed_results'):
                for filename, results_df in self._worker._processed_results:
                    logger.info(
                        "Processed analysis file %s (%d rows)", filename, len(results_df)
                    )
                    self.fitting_completed.emit(results_df)
            self.fitting_finished.emit(True, message)
        else:
            logger.error("Analysis fitting failed: %s", message)
            self.fitting_finished.emit(False, message)

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


class AnalysisFittingWorker(QObject):
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
        csv_file: Path,
        model_type: str,
        model_params: dict[str, float],
        model_bounds: dict[str, tuple[float, float]],
    ) -> None:
        """Initialize the analysis worker.

        Args:
            csv_file: Path to the CSV file to process
            model_type: Type of model to use for fitting
            model_params: Dictionary of model parameter values
            model_bounds: Dictionary of model parameter bounds
        """
        super().__init__()
        self._csv_file = csv_file
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
        Progress updates are logged in the core fitting service. Completion
        signals are emitted for UI coordination.
        """
        try:
            # Load and process the single CSV file
            if not self._csv_file.exists():
                self.finished.emit(False, f"CSV file not found: {self._csv_file}")
                return

            try:
                if self._is_cancelled:
                    return

                saved_csv_path: Path | None = None
                results_df: pd.DataFrame | None = None

                service = FittingService()
                results_df, saved_csv_path = service.fit_csv_file(
                    self._csv_file,
                    self._model_type,
                    model_params=self._model_params,
                    model_bounds=self._model_bounds,
                )

                if results_df is not None:
                    if not hasattr(self, "_processed_results"):
                        self._processed_results = []
                    self._processed_results.append((self._csv_file.name, results_df))
            except Exception as exc:
                error_msg = f"Failed to process {self._csv_file.name}: {exc}"
                logger.error(error_msg)
                self.finished.emit(False, error_msg)
                return

        except Exception as exc:
            logger.exception("Unexpected analysis worker failure")
            self.finished.emit(False, str(exc))
        else:
            # Success - emit finished with success message
            if saved_csv_path:
                message = f"Fitting completed. Saved results as {saved_csv_path.name}."
            else:
                message = f"Fitting completed. Processed {self._csv_file.name}."
            self.finished.emit(True, message)
