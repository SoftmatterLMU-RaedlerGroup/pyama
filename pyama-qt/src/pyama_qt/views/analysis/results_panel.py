"""Results panel rendering fitting quality and parameter histograms."""

from collections.abc import Iterable, Sequence
from pathlib import Path

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
)

from pyama_qt.config import DEFAULT_DIR
from ..base import BasePanel
from ..components.mpl_canvas import MplCanvas


class AnalysisResultsPanel(BasePanel):
    """Right-hand panel visualising fitting diagnostics."""

    parameter_selected = Signal(str)
    filter_toggled = Signal(bool)
    save_requested = Signal(Path)

    def build(self) -> None:
        layout = QVBoxLayout(self)
        self._results_group = self._build_results_group()
        layout.addWidget(self._results_group)

    def bind(self) -> None:
        self._param_combo.currentTextChanged.connect(self._on_param_changed)
        self._filter_checkbox.stateChanged.connect(self._on_filter_toggled)
        self._save_button.clicked.connect(self._on_save_clicked)

    # ------------------------------------------------------------------
    # Public API for controllers
    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Clear both charts."""
        self._quality_canvas.clear()
        self._param_canvas.clear()

    def render_quality_plot(
        self,
        lines: Iterable[tuple[Sequence[float], Sequence[float]]],
        styles: Iterable[dict],
        *,
        title: str,
        x_label: str,
        y_label: str,
        legend_text: str | None = None,
    ) -> None:
        """Render the fitting quality chart."""
        line_payload = tuple(lines)
        style_payload = tuple(styles)
        if not line_payload:
            self._quality_canvas.clear()
            return

        self._quality_canvas.plot_lines(
            line_payload,
            style_payload,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )

        if legend_text:
            ax = self._quality_canvas.axes
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

    def set_parameter_options(
        self, parameters: Sequence[str], *, current: str | None = None
    ) -> None:
        """Replace the parameter selector options."""
        self._param_combo.blockSignals(True)
        self._param_combo.clear()
        self._param_combo.addItems(parameters)
        if current and current in parameters:
            self._param_combo.setCurrentText(current)
        self._param_combo.blockSignals(False)

    def current_parameter(self) -> str:
        """Return the currently selected parameter name."""
        return self._param_combo.currentText()

    def is_filter_enabled(self) -> bool:
        """Return True when 'Good Fits Only' is checked."""
        return self._filter_checkbox.isChecked()

    def set_filter_enabled(self, enabled: bool) -> None:
        """Update the checkbox state programmatically."""
        self._filter_checkbox.setChecked(enabled)

    def render_histogram(
        self,
        *,
        param_name: str,
        values: Sequence[float],
        bins: int = 30,
        x_label: str | None = None,
        y_label: str = "Frequency",
    ) -> None:
        """Render the parameter histogram."""
        if not values:
            self._param_canvas.clear()
            return

        self._param_canvas.plot_histogram(
            list(values),
            bins=bins,
            title=f"Distribution of {param_name}",
            x_label=x_label or param_name,
            y_label=y_label,
        )

    def export_histogram(self, path: Path, *, dpi: int = 300) -> None:
        """Save the current histogram figure to disk."""
        self._param_canvas.figure.savefig(path, dpi=dpi, bbox_inches="tight")

    # ------------------------------------------------------------------
    # Internal event handlers
    # ------------------------------------------------------------------
    def _on_param_changed(self, name: str) -> None:
        if name:
            self.parameter_selected.emit(name)

    def _on_filter_toggled(self, state: int) -> None:
        self.filter_toggled.emit(bool(state))

    def _on_save_clicked(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select folder to save histograms",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if folder_path:
            self.save_requested.emit(Path(folder_path))

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------
    def _build_results_group(self) -> QGroupBox:
        group = QGroupBox("Results")
        layout = QVBoxLayout(group)

        layout.addWidget(QLabel("Fitting Quality"))
        self._quality_canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self._quality_canvas)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Parameter:"))
        self._param_combo = QComboBox()
        controls.addWidget(self._param_combo)

        controls.addStretch()
        self._filter_checkbox = QCheckBox("Good Fits Only")
        controls.addWidget(self._filter_checkbox)

        self._save_button = QPushButton("Save Plot")
        controls.addWidget(self._save_button)

        layout.addLayout(controls)

        self._param_canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self._param_canvas)

        return group
