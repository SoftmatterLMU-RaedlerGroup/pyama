"""Results panel rendering parameter histograms and scatter plots."""

import logging
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_qt.components.mpl_canvas import MplCanvas
from pyama_qt.constants import DEFAULT_DIR

logger = logging.getLogger(__name__)


class ParameterPanel(QWidget):
    """Right-hand panel visualising parameter distributions and correlations.

    This panel provides an interface for analyzing fitted parameter results,
    including histograms of individual parameters and scatter plots showing
    correlations between parameters. It supports filtering by fitting quality
    and saving all plots to files.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    results_loaded = Signal(
        object
    )  # Emitted when results are loaded from file (pd.DataFrame)
    plot_saved = Signal(str, str)  # Emitted when a plot is saved (filename, directory)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the parameter panel.

        Args:
            *args: Positional arguments passed to parent QWidget
            **kwargs: Keyword arguments passed to parent QWidget
        """
        super().__init__(*args, **kwargs)
        self._build_ui()
        self._connect_signals()

        # State from FittedResultsModel
        self._results_df: pd.DataFrame | None = None

        # State from Controller
        self._parameter_names: list[str] = []
        self._selected_parameter: str | None = None
        self._x_parameter: str | None = None
        self._y_parameter: str | None = None

        # UI Components
        self._param_group: QGroupBox | None = None

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout.

        Creates a vertical layout with a parameter analysis group containing
        filter controls, histogram and scatter plot canvases, and save controls.
        """
        layout = QVBoxLayout(self)
        self._param_group = self._build_param_group()
        layout.addWidget(self._param_group)

    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers.

        Sets up all the signal/slot connections for user interactions,
        including parameter selection, filtering, and plot saving.
        """
        self._param_combo.currentTextChanged.connect(self._on_param_changed)
        self._filter_checkbox.stateChanged.connect(self._on_filter_changed)
        self._hist_save_button.clicked.connect(self._on_hist_save_clicked)
        self._scatter_save_button.clicked.connect(self._on_scatter_save_clicked)

        # Connect scatter plot parameter selections
        self._x_param_combo.currentTextChanged.connect(self._on_x_param_changed)
        self._y_param_combo.currentTextChanged.connect(self._on_y_param_changed)

    def _build_param_group(self) -> QGroupBox:
        """Build the parameter analysis group.

        Returns:
            QGroupBox containing all parameter analysis controls and canvases
        """
        group = QGroupBox("Parameter Analysis")
        layout = QVBoxLayout(group)

        # Top controls: Good Fits Only checkbox only
        top_controls = QHBoxLayout()
        self._filter_checkbox = QCheckBox("Good fits only (R² > 0.9)")
        top_controls.addWidget(self._filter_checkbox)
        layout.addLayout(top_controls)

        # Histogram controls (parameter dropdown)
        hist_controls = QHBoxLayout()
        hist_controls.addWidget(QLabel("Single Parameter:"))
        self._param_combo = QComboBox()
        hist_controls.addWidget(self._param_combo)
        layout.addLayout(hist_controls)

        # Histogram canvas
        self._param_canvas = MplCanvas(self)
        layout.addWidget(self._param_canvas)

        # Histogram save button
        hist_save_layout = QHBoxLayout()
        self._hist_save_button = QPushButton("Save Histogram")
        hist_save_layout.addWidget(self._hist_save_button)
        layout.addLayout(hist_save_layout)

        # Scatter plot controls (X and Y parameter dropdowns)
        scatter_controls = QHBoxLayout()
        scatter_controls.addWidget(QLabel("Double Parameter:"))
        self._x_param_combo = QComboBox()
        scatter_controls.addWidget(self._x_param_combo)
        self._y_param_combo = QComboBox()
        scatter_controls.addWidget(self._y_param_combo)
        layout.addLayout(scatter_controls)

        # Scatter plot canvas
        self._scatter_canvas = MplCanvas(self)
        layout.addWidget(self._scatter_canvas)

        # Scatter plot save button
        scatter_save_layout = QHBoxLayout()
        self._scatter_save_button = QPushButton("Save Scatter Plot")
        scatter_save_layout.addWidget(self._scatter_save_button)
        layout.addLayout(scatter_save_layout)

        return group

    # ------------------------------------------------------------------------
    # PUBLIC SLOTS
    # ------------------------------------------------------------------------
    @Slot(object)
    def on_fitting_completed(self, results_df: pd.DataFrame) -> None:
        """Handle fitting completion event.

        Args:
            results_df: DataFrame containing fitting results
        """
        self.set_results(results_df)

    @Slot(object)
    def on_load_fitted_results(self, path: Path) -> None:
        """Handle loading fitted results from file.

        Args:
            path: Path to the fitted results CSV file
        """
        try:
            df = pd.read_csv(path)
            self.set_results(df)
            logger.info("Loaded existing fitted results from %s", path)
        except Exception as e:
            logger.warning("Failed to load fitted results from %s: %s", path, e)
            self.clear()

    # ------------------------------------------------------------------------
    # INTERNAL LOGIC
    # ------------------------------------------------------------------------
    def set_results(self, df: pd.DataFrame) -> None:
        """Set the results DataFrame and update UI.

        Args:
            df: DataFrame containing fitting results
        """
        self._results_df = df
        if df is None or df.empty:
            self.clear()
            return

        self._parameter_names = self._discover_numeric_parameters(df)

        # Update parameter combo box
        self._param_combo.blockSignals(True)
        self._param_combo.clear()
        self._param_combo.addItems(self._parameter_names)
        if self._parameter_names:
            self._selected_parameter = self._parameter_names[0]
            self._param_combo.setCurrentIndex(0)
        self._param_combo.blockSignals(False)

        # Update scatter plot parameter combo boxes
        for combo, attr, default_idx in [
            (self._x_param_combo, "_x_parameter", 0),
            (self._y_param_combo, "_y_parameter", 1),
        ]:
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(self._parameter_names)

            # Set default selection
            if self._parameter_names:
                idx = min(default_idx, len(self._parameter_names) - 1)
                setattr(self, attr, self._parameter_names[idx])
                combo.setCurrentIndex(idx)

            combo.blockSignals(False)

        self._update_histogram()
        self._update_scatter_plot()

    def clear(self) -> None:
        """Clear all data and reset UI state."""
        self._results_df = None
        self._parameter_names = []
        self._selected_parameter = None
        self._x_parameter = None
        self._y_parameter = None
        self._param_canvas.clear()
        self._scatter_canvas.clear()
        self._param_combo.clear()
        self._x_param_combo.clear()
        self._y_param_combo.clear()

    def _plot_parameter_histogram(self, param_name: str, series) -> None:
        """Plot parameter histogram with consistent styling.

        Args:
            param_name: Name of the parameter
            series: Series containing parameter values
        """
        self._param_canvas.plot_histogram(
            series.tolist(),
            bins=30,
            x_label=param_name,
            y_label="Frequency",
        )

    def _update_histogram(self) -> None:
        """Update the histogram plot with current selection."""
        if self._results_df is None or not self._selected_parameter:
            self._param_canvas.clear()
            return

        series = self._get_histogram_series(self._results_df, self._selected_parameter)
        if series is None or series.empty:
            self._param_canvas.clear()
            return

        self._plot_parameter_histogram(self._selected_parameter, series)

    def _plot_scatter_plot(self, x_param: str, y_param: str, x_data, y_data) -> None:
        """Plot scatter plot with consistent styling.

        Args:
            x_param: Name of the x-axis parameter
            y_param: Name of the y-axis parameter
            x_data: Series containing x-axis values
            y_data: Series containing y-axis values
        """
        # Drop NaN values
        valid_mask = ~(x_data.isna() | y_data.isna())
        x_values = x_data[valid_mask].tolist()
        y_values = y_data[valid_mask].tolist()

        if not x_values or not y_values:
            self._scatter_canvas.clear()
            return

        # Create scatter plot
        lines = [(x_values, y_values)]
        styles = [{"plot_style": "scatter", "alpha": 0.6, "s": 20}]

        self._scatter_canvas.plot_lines(
            lines,
            styles,
            x_label=x_param,
            y_label=y_param,
        )

    def _update_scatter_plot(self) -> None:
        """Update the scatter plot with current selection."""
        if (
            self._results_df is None
            or not self._x_parameter
            or not self._y_parameter
            or self._x_parameter not in self._results_df.columns
            or self._y_parameter not in self._results_df.columns
        ):
            self._scatter_canvas.clear()
            return

        # Get the x and y parameter data
        x_data = pd.to_numeric(self._results_df[self._x_parameter], errors="coerce")
        y_data = pd.to_numeric(self._results_df[self._y_parameter], errors="coerce")

        # Apply filter if needed
        if (
            self._filter_checkbox.isChecked()
            and "r_squared" in self._results_df.columns
        ):
            mask = pd.to_numeric(self._results_df["r_squared"], errors="coerce") > 0.9
            x_data = x_data[mask]
            y_data = y_data[mask]

        self._plot_scatter_plot(self._x_parameter, self._y_parameter, x_data, y_data)

    def _get_histogram_series(
        self, df: pd.DataFrame, param_name: str
    ) -> pd.Series | None:
        """Get histogram data series for a parameter.

        Args:
            df: DataFrame containing parameter data
            param_name: Name of the parameter

        Returns:
            Series containing parameter values or None if no data
        """
        data = pd.to_numeric(df.get(param_name), errors="coerce").dropna()
        if data.empty:
            return None

        if self._filter_checkbox.isChecked() and "r_squared" in df.columns:
            mask = pd.to_numeric(df["r_squared"], errors="coerce") > 0.9
            data = pd.to_numeric(df.loc[mask, param_name], errors="coerce").dropna()

        return data if not data.empty else None

    def _discover_numeric_parameters(self, df: pd.DataFrame) -> list[str]:
        """Discover numeric parameters in the DataFrame.

        Args:
            df: DataFrame to analyze

        Returns:
            List of numeric parameter column names
        """
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
        return [
            col
            for col in df.columns
            if col not in metadata_cols
            and pd.to_numeric(df[col], errors="coerce").notna().any()
        ]

    # ------------------------------------------------------------------------
    # UI EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot(str)
    def _on_param_changed(self, name: str) -> None:
        """Handle parameter selection change.

        Args:
            name: Name of the selected parameter
        """
        logger.debug("UI Event: Parameter changed to - %s", name)
        if name and name != self._selected_parameter:
            self._selected_parameter = name
            self._update_histogram()

    @Slot(str)
    def _on_x_param_changed(self, name: str) -> None:
        """Handle x-axis parameter selection change.

        Args:
            name: Name of the selected x-axis parameter
        """
        logger.debug("UI Event: X parameter changed to - %s", name)
        if name and name != self._x_parameter:
            self._x_parameter = name
            self._update_scatter_plot()

    @Slot(str)
    def _on_y_param_changed(self, name: str) -> None:
        """Handle y-axis parameter selection change.

        Args:
            name: Name of the selected y-axis parameter
        """
        logger.debug("UI Event: Y parameter changed to - %s", name)
        if name and name != self._y_parameter:
            self._y_parameter = name
            self._update_scatter_plot()

    @Slot()
    def _on_filter_changed(self) -> None:
        """Handle filter checkbox change."""
        logger.debug("UI Event: Filter checkbox changed")
        self._update_histogram()
        self._update_scatter_plot()

    @Slot()
    def _on_hist_save_clicked(self) -> None:
        """Handle histogram save button click.

        Opens a file dialog to select a save location and saves the current histogram.
        """
        logger.debug("UI Click: Save histogram button")
        if not self._selected_parameter:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Histogram",
            str(Path(DEFAULT_DIR) / f"{self._selected_parameter}.png"),
            "PNG Files (*.png)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            logger.debug("UI Action: Saving histogram to - %s", file_path)
            self._save_current_histogram(Path(file_path))

    @Slot()
    def _on_scatter_save_clicked(self) -> None:
        """Handle scatter plot save button click.

        Opens a file dialog to select a save location and saves the current scatter plot.
        """
        logger.debug("UI Click: Save scatter plot button")
        if not self._x_parameter or not self._y_parameter:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scatter Plot",
            str(Path(DEFAULT_DIR) / f"{self._x_parameter}_vs_{self._y_parameter}.png"),
            "PNG Files (*.png)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            logger.debug("UI Action: Saving scatter plot to - %s", file_path)
            self._save_current_scatter_plot(Path(file_path))

    def _save_current_histogram(self, file_path: Path) -> None:
        """Save the current histogram to the specified file.

        Args:
            file_path: Path where the histogram will be saved
        """
        if self._results_df is None or not self._selected_parameter:
            return

        series = self._get_histogram_series(self._results_df, self._selected_parameter)
        if series is None or series.empty:
            return

        # Ensure the histogram is rendered before saving
        self._plot_parameter_histogram(self._selected_parameter, series)
        self._param_canvas.figure.savefig(file_path, dpi=300, bbox_inches="tight")
        logger.info("Saved histogram to %s", file_path)
        self.plot_saved.emit(file_path.name, str(file_path.parent))

    def _save_current_scatter_plot(self, file_path: Path) -> None:
        """Save the current scatter plot to the specified file.

        Args:
            file_path: Path where the scatter plot will be saved
        """
        if (
            self._results_df is None
            or not self._x_parameter
            or not self._y_parameter
            or self._x_parameter not in self._results_df.columns
            or self._y_parameter not in self._results_df.columns
        ):
            return

        # Get the x and y parameter data
        x_data = pd.to_numeric(self._results_df[self._x_parameter], errors="coerce")
        y_data = pd.to_numeric(self._results_df[self._y_parameter], errors="coerce")

        # Apply filter if needed
        if (
            self._filter_checkbox.isChecked()
            and "r_squared" in self._results_df.columns
        ):
            mask = pd.to_numeric(self._results_df["r_squared"], errors="coerce") > 0.9
            x_data = x_data[mask]
            y_data = y_data[mask]

        # Ensure the scatter plot is rendered before saving
        self._plot_scatter_plot(self._x_parameter, self._y_parameter, x_data, y_data)
        self._scatter_canvas.figure.savefig(file_path, dpi=300, bbox_inches="tight")
        logger.info("Saved scatter plot to %s", file_path)
        self.plot_saved.emit(file_path.name, str(file_path.parent))
