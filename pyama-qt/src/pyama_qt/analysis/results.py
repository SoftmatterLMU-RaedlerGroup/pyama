"""Results panel rendering parameter histograms and scatter plots."""

import logging
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Signal
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

from pyama_qt.constants import DEFAULT_DIR

from ..components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


class ResultsPanel(QWidget):
    """Right-hand panel visualising parameter distributions and correlations."""

    # Signals
    results_loaded = Signal(object)  # pd.DataFrame - when results are loaded from file
    status_message = Signal(str)  # Status message for UI

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.build()
        self.bind()
        # --- State from FittedResultsModel ---
        self._results_df: pd.DataFrame | None = None

        # --- State from Controller ---
        self._parameter_names: list[str] = []
        self._selected_parameter: str | None = None
        self._x_parameter: str | None = None  # For scatter plots
        self._y_parameter: str | None = None  # For scatter plots

        # --- UI Components ---
        self._param_group: QGroupBox | None = None

    def build(self) -> None:
        layout = QVBoxLayout(self)
        self._param_group = self._build_param_group()
        layout.addWidget(self._param_group)

    def _build_param_group(self) -> QGroupBox:
        group = QGroupBox("Parameter Analysis")
        layout = QVBoxLayout(group)

        # Top controls: Good Fits Only checkbox, Load button, and Save button
        top_controls = QHBoxLayout()
        self._filter_checkbox = QCheckBox("Good Fits Only (R² > 0.9)")
        top_controls.addWidget(self._filter_checkbox)
        self._load_button = QPushButton("Load Fitted Results")
        top_controls.addWidget(self._load_button)
        self._save_button = QPushButton("Save All Plots")
        top_controls.addWidget(self._save_button)
        top_controls.addStretch()
        layout.addLayout(top_controls)

        # Histogram controls (parameter dropdown)
        hist_controls = QHBoxLayout()
        hist_controls.addWidget(QLabel("Single Parameter:"))
        self._param_combo = QComboBox()
        hist_controls.addWidget(self._param_combo)
        hist_controls.addStretch()
        layout.addLayout(hist_controls)

        # Histogram canvas
        self._param_canvas = MplCanvas(self)  # Reduced height

        layout.addWidget(self._param_canvas)

        # Scatter plot controls (X and Y parameter dropdowns)
        scatter_controls = QHBoxLayout()
        scatter_controls.addWidget(QLabel("Double Parameter:"))
        self._x_param_combo = QComboBox()
        scatter_controls.addWidget(self._x_param_combo)
        self._y_param_combo = QComboBox()
        scatter_controls.addWidget(self._y_param_combo)
        scatter_controls.addStretch()
        layout.addLayout(scatter_controls)

        # Scatter plot canvas
        self._scatter_canvas = MplCanvas(self)  # Lower half
        layout.addWidget(self._scatter_canvas)

        return group

    def bind(self) -> None:
        self._param_combo.currentTextChanged.connect(self._on_param_changed)
        self._filter_checkbox.stateChanged.connect(lambda: self._update_histogram())
        self._load_button.clicked.connect(self._on_load_clicked)
        self._save_button.clicked.connect(self._on_save_clicked)

        # Connect scatter plot parameter selections
        self._x_param_combo.currentTextChanged.connect(self._on_x_param_changed)
        self._y_param_combo.currentTextChanged.connect(self._on_y_param_changed)

    # --- Public Slots for connection to other components ---
    def on_fitting_completed(self, results_df: pd.DataFrame):
        self.set_results(results_df)

    def on_load_fitted_results(self, path: Path):
        try:
            df = pd.read_csv(path)
            self.set_results(df)
            logger.info("Loaded existing fitted results from %s", path)
        except Exception as e:
            logger.warning("Failed to load fitted results from %s: %s", path, e)
            self.clear()

    # --- Internal Logic (from Model and Controller) ---
    def set_results(self, df: pd.DataFrame):
        self._results_df = df
        if df is None or df.empty:
            self.clear()
            return

        self._parameter_names = self._discover_numeric_parameters(df)

        current = self._selected_parameter
        if current not in self._parameter_names:
            current = self._parameter_names[0] if self._parameter_names else None
        self._selected_parameter = current

        # Update all parameter combo boxes
        self._param_combo.blockSignals(True)
        self._param_combo.clear()
        self._param_combo.addItems(self._parameter_names)
        if current:
            self._param_combo.setCurrentText(current)
        self._param_combo.blockSignals(False)

        # Update scatter plot parameter combo boxes
        self._x_param_combo.blockSignals(True)
        self._x_param_combo.clear()
        self._x_param_combo.addItems(self._parameter_names)
        if self._x_parameter and self._x_parameter in self._parameter_names:
            self._x_param_combo.setCurrentText(self._x_parameter)
        elif self._parameter_names:
            self._x_parameter = self._parameter_names[0]
            self._x_param_combo.setCurrentText(self._x_parameter)
        self._x_param_combo.blockSignals(False)

        self._y_param_combo.blockSignals(True)
        self._y_param_combo.clear()
        self._y_param_combo.addItems(self._parameter_names)
        if self._y_parameter and self._y_parameter in self._parameter_names:
            self._y_param_combo.setCurrentText(self._y_parameter)
        elif len(self._parameter_names) > 1:
            self._y_parameter = (
                self._parameter_names[1]
                if len(self._parameter_names) > 1
                else self._parameter_names[0]
            )
            self._y_param_combo.setCurrentText(self._y_parameter)
        self._y_param_combo.blockSignals(False)

        self._update_histogram()
        self._update_scatter_plot()

    def clear(self):
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

    def _update_histogram(self):
        if self._results_df is None or not self._selected_parameter:
            self._param_canvas.clear()
            return

        series = self._get_histogram_series(self._results_df, self._selected_parameter)
        if series is None or series.empty:
            self._param_canvas.clear()
            return

        self._param_canvas.plot_histogram(
            series.tolist(),
            bins=30,
            title=f"Distribution of {self._selected_parameter}",
            x_label=self._selected_parameter,
            y_label="Frequency",
        )

    def _update_scatter_plot(self):
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

        title = f"Scatter Plot: {self._x_parameter} vs {self._y_parameter}"

        self._scatter_canvas.plot_lines(
            lines,
            styles,
            title=title,
            x_label=self._x_parameter,
            y_label=self._y_parameter,
        )

    def _get_histogram_series(
        self, df: pd.DataFrame, param_name: str
    ) -> pd.Series | None:
        data = pd.to_numeric(df.get(param_name), errors="coerce").dropna()
        if data.empty:
            return None

        if self._filter_checkbox.isChecked() and "r_squared" in df.columns:
            mask = pd.to_numeric(df["r_squared"], errors="coerce") > 0.9
            data = pd.to_numeric(df.loc[mask, param_name], errors="coerce").dropna()

        return data if not data.empty else None

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
        return [
            col
            for col in df.columns
            if col not in metadata_cols
            and pd.to_numeric(df[col], errors="coerce").notna().any()
        ]

    # --- UI Event Handlers ---
    def _on_param_changed(self, name: str):
        logger.debug("UI Event: Parameter changed to - %s", name)
        if name and name != self._selected_parameter:
            self._selected_parameter = name
            self._update_histogram()

    def _on_x_param_changed(self, name: str):
        logger.debug("UI Event: X parameter changed to - %s", name)
        if name and name != self._x_parameter:
            self._x_parameter = name
            self._update_scatter_plot()

    def _on_y_param_changed(self, name: str):
        logger.debug("UI Event: Y parameter changed to - %s", name)
        if name and name != self._y_parameter:
            self._y_parameter = name
            self._update_scatter_plot()

    def _on_load_clicked(self):
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
            self.on_load_fitted_results(Path(file_path))
            self.status_message.emit(f"Loaded fitted results from {Path(file_path).name}")

    def _on_save_clicked(self):
        logger.debug("UI Click: Save histograms button")
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select folder to save histograms",
            str(DEFAULT_DIR),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if folder_path:
            logger.debug("UI Action: Saving histograms to - %s", folder_path)
            self._save_all_histograms(Path(folder_path))

    def _save_all_histograms(self, folder: Path):
        if self._results_df is None or self._results_df.empty:
            return

        current_param = self._selected_parameter
        for param_name in self._parameter_names:
            series = self._get_histogram_series(self._results_df, param_name)
            if series is None or series.empty:
                continue
            # Temporarily render histogram to save it
            self._param_canvas.plot_histogram(
                series.tolist(),
                title=f"Distribution of {param_name}",
                x_label=param_name,
            )
            output_path = folder / f"{param_name}.png"
            self._param_canvas.figure.savefig(output_path, dpi=300, bbox_inches="tight")
            logger.info("Saved histogram to %s", output_path)

        # Restore the originally selected histogram
        if current_param:
            self._selected_parameter = current_param
            self._update_histogram()
