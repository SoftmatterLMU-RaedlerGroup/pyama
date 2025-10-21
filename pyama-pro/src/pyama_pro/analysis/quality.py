"""Fitting quality inspection panel."""

import logging

import pandas as pd
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_core.analysis.fitting import (
    get_trace,
    analyze_fitting_quality,
)
from pyama_core.analysis.models import get_model
from pyama_pro.components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


class QualityPanel(QWidget):
    """Middle panel visualising fitting diagnostics and individual fits.

    This panel provides an interface for inspecting the quality of model
    fits, including a quality plot showing R² values across all cells
    and trace visualization showing raw data with fitted curves for
    individual cells.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    cell_visualized = Signal(str)  # Emitted when a cell is visualized (cell ID)
    shuffle_requested = Signal()  # Emitted to request a random cell from data panel
    fitting_completed = Signal(object)  # Emitted when fitting completes (pd.DataFrame)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the quality panel.

        Args:
            *args: Positional arguments passed to parent QWidget
            **kwargs: Keyword arguments passed to parent QWidget
        """
        super().__init__(*args, **kwargs)
        self._build_ui()
        self._connect_signals()

        # State
        self._results_df: pd.DataFrame | None = None
        self._raw_data: pd.DataFrame | None = None
        self._selected_cell: str | None = None

        # UI Components
        self._qc_group: QGroupBox | None = None
        self._trace_group: QGroupBox | None = None

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout.

        Creates a vertical layout with two main groups:
        1. Quality plot group for displaying fitting quality metrics
        2. Trace visualization group for displaying individual cell traces
        """
        layout = QVBoxLayout(self)

        # Add quality plot group
        self._qc_group = self._build_qc_group()
        layout.addWidget(self._qc_group)

        # Add trace visualization group
        self._trace_group = self._build_trace_group()
        layout.addWidget(self._trace_group)

    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers.

        Sets up the signal/slot connection for the shuffle button.
        """
        self._shuffle_button.clicked.connect(self._on_shuffle_clicked)

    def _build_qc_group(self) -> QGroupBox:
        """Build the quality plot group.

        Returns:
            QGroupBox containing the quality plot canvas
        """
        group = QGroupBox("Fitting Quality")
        layout = QVBoxLayout(group)

        # Quality plot on top
        self._qc_canvas = MplCanvas(self)
        layout.addWidget(self._qc_canvas)

        return group

    def _build_trace_group(self) -> QGroupBox:
        """Build the trace visualization group.

        Returns:
            QGroupBox containing the trace plot canvas and shuffle button
        """
        group = QGroupBox("Fitted Traces")
        layout = QVBoxLayout(group)

        # Add shuffle button for trace visualization
        controls_layout = QHBoxLayout()
        self._shuffle_button = QPushButton("Show Random Trace")
        controls_layout.addWidget(self._shuffle_button)
        layout.addLayout(controls_layout)

        self._trace_canvas = MplCanvas(self)
        layout.addWidget(self._trace_canvas)

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
    def on_raw_data_changed(self, df: pd.DataFrame) -> None:
        """Handle raw data change event.

        Args:
            df: DataFrame containing raw trace data
        """
        self._raw_data = df
        if self._selected_cell:
            self._update_trace_plot(self._selected_cell)

    @Slot(object)
    def on_shuffle_requested(self, get_random_cell_func) -> None:
        """Shuffle visualization to a random cell.

        Args:
            get_random_cell_func: Function to get a random cell ID
        """
        logger.debug("UI Event: Shuffle requested")
        cell_id = get_random_cell_func()
        if cell_id:
            logger.debug("UI Action: Selected random cell - %s", cell_id)
            self._selected_cell = cell_id
            self._update_trace_plot(cell_id)
            self.cell_visualized.emit(cell_id)
        else:
            logger.debug("UI Action: No cells available for shuffle")

    @Slot()
    def _on_shuffle_clicked(self) -> None:
        """Handle shuffle button click.

        Emits the shuffle_requested signal to request a random cell
        from the data panel.
        """
        logger.debug("UI Click: Shuffle button")
        self.shuffle_requested.emit()

    @Slot(object)
    def on_fitted_results_changed(self, results_df: pd.DataFrame) -> None:
        """Handle fitted results change event.

        Args:
            results_df: DataFrame containing fitted results
        """
        self.set_results(results_df)

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

        self._update_quality_plot()

    def clear(self) -> None:
        """Clear all data and reset UI state."""
        self._results_df = None
        self._raw_data = None
        self._qc_canvas.clear()
        self._trace_canvas.clear()
        self._selected_cell = None

    def _update_quality_plot(self) -> None:
        """Update the quality plot with current results."""
        if self._results_df is None or "r_squared" not in self._results_df.columns:
            self._qc_canvas.clear()
            return

        quality_metrics = analyze_fitting_quality(self._results_df)
        if not quality_metrics:
            self._qc_canvas.clear()
            return

        r_squared_values = quality_metrics["r_squared_values"]
        cell_indices = quality_metrics["cell_indices"]
        colors = quality_metrics["colors"]

        lines = [(cell_indices, r_squared_values)]
        styles = [{"plot_style": "scatter", "color": colors, "alpha": 0.6, "s": 20}]

        good_pct = quality_metrics["good_percentage"]
        fair_pct = quality_metrics["fair_percentage"]
        poor_pct = quality_metrics["poor_percentage"]

        legend_text = f"Good (R²>0.9): {good_pct:.1f}%\nFair (0.7<R²≤0.9): {fair_pct:.1f}%\nPoor (R²≤0.7): {poor_pct:.1f}%"

        self._qc_canvas.plot_lines(lines, styles, x_label="Cell Index", y_label="R²")
        ax = self._qc_canvas._axes
        if ax:
            props = dict(boxstyle="round", facecolor="white", alpha=0.8)
            ax.text(
                0.98,
                0.02,
                legend_text,
                transform=ax.transAxes,
                fontsize=9,
                verticalalignment="bottom",
                horizontalalignment="right",
                bbox=props,
            )

    def _update_trace_plot(self, cell_id: str) -> None:
        """Update the trace plot with raw data and fitted curve.

        Args:
            cell_id: ID of the cell to visualize
        """
        if self._raw_data is None or cell_id not in self._raw_data.columns:
            self._trace_canvas.clear()
            return

        # Get the raw trace data
        time_data, trace_data = get_trace(self._raw_data, cell_id)

        # Prepare to get fitted parameters if available
        fitted_params = None
        model_type = None
        success = None

        if self._results_df is not None:
            # Find the corresponding row in results for this cell_id
            # Try both string and integer matching for backward compatibility
            result_row = self._results_df[self._results_df["cell_id"] == cell_id]

            # If no match with string, try converting to int for backward compatibility
            if result_row.empty:
                try:
                    cell_id_int = int(cell_id)
                    result_row = self._results_df[
                        self._results_df["cell_id"] == cell_id_int
                    ]
                except ValueError:
                    pass

            if not result_row.empty:
                result_row = result_row.iloc[0]
                if "model_type" in result_row:
                    model_type = result_row["model_type"]
                if "success" in result_row:
                    success = result_row["success"]

                # Get fitted parameters (excluding special columns)
                special_cols = {"cell_id", "model_type", "success", "r_squared"}
                fitted_params = {
                    col: result_row[col]
                    for col in result_row.index
                    if col not in special_cols and pd.notna(result_row[col])
                }

        # Create the plot
        lines_data = []
        styles_data = []

        # Plot raw data
        lines_data.append((time_data, trace_data))
        styles_data.append(
            {"color": "blue", "alpha": 0.7, "label": cell_id, "linewidth": 1}
        )

        # Plot fitted curve if parameters are available and fitting was successful
        if fitted_params and model_type and success:
            try:
                model = get_model(model_type)
                params_obj = model.Params(**fitted_params)
                fitted_trace = model.eval(time_data, params_obj)

                lines_data.append((time_data, fitted_trace))
                styles_data.append(
                    {"color": "red", "alpha": 0.8, "label": "Fitted", "linewidth": 2}
                )
            except Exception as e:
                logger.warning(
                    f"Could not generate fitted curve for cell {cell_id}: {e}"
                )

        self._render_trace_plot_internal(
            lines_data,
            styles_data,
            x_label="Time (hours)",
            y_label="Intensity",
        )

    def _render_trace_plot_internal(
        self,
        lines_data: list,
        styles_data: list,
        *,
        x_label: str = "Time (hours)",
        y_label: str = "Intensity",
    ) -> None:
        """Internal method to render the trace plot.

        Args:
            lines_data: List of line data tuples (x, y)
            styles_data: List of style dictionaries
            x_label: X-axis label
            y_label: Y-axis label
        """
        self._trace_canvas.plot_lines(
            lines_data,
            styles_data,
            x_label=x_label,
            y_label=y_label,
        )
