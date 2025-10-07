"""Input/configuration panel for the processing workflow."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from pyama_qt.config import DEFAULT_DIR
from ..base import BasePanel
from ..components.parameter_panel import ParameterPanel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChannelSelectionPayload:
    """Lightweight payload describing selected channels."""

    phase: int | None
    fluorescence: list[int]


class ProcessingConfigPanel(BasePanel):
    """Collects user inputs for running the processing workflow."""

    file_selected = Signal(Path)
    output_dir_selected = Signal(Path)
    channels_changed = Signal(object)  # Emits ChannelSelectionPayload as dict-like
    parameters_changed = Signal(dict)  # raw values
    process_requested = Signal()

    def build(self) -> None:
        layout = QHBoxLayout(self)

        self._input_group = self._build_input_group()
        self._output_group = self._build_output_group()

        layout.addWidget(self._input_group, 1)
        layout.addWidget(self._output_group, 1)

        self._progress_bar.setVisible(False)

    def bind(self) -> None:
        self._nd2_button.clicked.connect(self._on_microscopy_clicked)
        self._output_button.clicked.connect(self._on_output_clicked)
        self._process_button.clicked.connect(self.process_requested.emit)
        self._pc_combo.currentIndexChanged.connect(self._emit_channel_selection)
        self._fl_list.itemClicked.connect(self._on_fl_item_clicked)
        self._fl_list.itemSelectionChanged.connect(self._emit_channel_selection)
        self._param_panel.parameters_changed.connect(self._on_parameters_changed)

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------
    def _build_input_group(self) -> QGroupBox:
        group = QGroupBox("Input")
        layout = QVBoxLayout(group)

        header = QHBoxLayout()
        header.addWidget(QLabel("Microscopy File:"))
        header.addStretch()
        self._nd2_button = QPushButton("Browse")
        header.addWidget(self._nd2_button)
        layout.addLayout(header)

        self._microscopy_path_field = QLineEdit()
        self._microscopy_path_field.setReadOnly(True)
        layout.addWidget(self._microscopy_path_field)

        self._channel_container = self._build_channel_section()
        layout.addWidget(self._channel_container)

        return group

    def _build_channel_section(self) -> QGroupBox:
        group = QGroupBox("Channels")
        layout = QVBoxLayout(group)

        pc_layout = QVBoxLayout()
        pc_layout.addWidget(QLabel("Phase Contrast"))
        self._pc_combo = QComboBox()
        self._pc_combo.addItem("None", None)
        pc_layout.addWidget(self._pc_combo)
        layout.addLayout(pc_layout)

        fl_layout = QVBoxLayout()
        fl_layout.addWidget(QLabel("Fluorescence (multi-select)"))
        self._fl_list = QListWidget()
        # Configure for multi-selection without needing modifier keys
        self._fl_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._fl_list.setSelectionBehavior(QListWidget.SelectionBehavior.SelectItems)
        self._fl_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Keep the widget interactive by default; avoid explicit enable/disable calls.
        self._fl_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._fl_list.setMouseTracking(True)
        fl_layout.addWidget(self._fl_list)
        layout.addLayout(fl_layout)

        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("Output")
        layout = QVBoxLayout(group)

        header = QHBoxLayout()
        header.addWidget(QLabel("Save Directory:"))
        header.addStretch()
        self._output_button = QPushButton("Browse")
        header.addWidget(self._output_button)
        layout.addLayout(header)

        self._output_dir_field = QLineEdit()
        self._output_dir_field.setReadOnly(True)
        layout.addWidget(self._output_dir_field)

        self._param_panel = ParameterPanel()
        self._initialize_parameter_defaults()
        layout.addWidget(self._param_panel)

        self._process_button = QPushButton("Start Complete Workflow")
        # Avoid starting with explicit disabled state here; callers/controllers
        # will manage interactivity based on state updates.
        layout.addWidget(self._process_button)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        return group

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_microscopy_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Microscopy File",
            DEFAULT_DIR,
            "Microscopy Files (*.nd2 *.czi);;ND2 Files (*.nd2);;CZI Files (*.czi);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            logger.info("Microscopy file chosen: %s", file_path)
            self.file_selected.emit(Path(file_path))

    def _on_output_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            DEFAULT_DIR,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            logger.info("Output directory chosen: %s", directory)
            self.output_dir_selected.emit(Path(directory))

    def _on_fl_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle individual item clicks in the fluorescence list."""
        # With MultiSelection mode, clicks automatically toggle selection
        # Just emit the channel selection change
        self._emit_channel_selection()

    def _emit_channel_selection(self) -> None:
        if self._pc_combo.count() == 0:
            return

        phase_data = self._pc_combo.currentData()
        phase = int(phase_data) if isinstance(phase_data, int) else None

        fluorescence = [
            int(item.data(Qt.ItemDataRole.UserRole))
            for item in self._fl_list.selectedItems()
        ]
        payload = ChannelSelectionPayload(phase=phase, fluorescence=fluorescence)
        self.channels_changed.emit(payload)

    def _on_parameters_changed(self) -> None:
        df = self._param_panel.get_values_df()
        if df is not None:
            # Convert DataFrame to simple dict: parameter_name -> value
            values = (
                df["value"].to_dict()
                if "value" in df.columns
                else df.iloc[:, 0].to_dict()
            )
            self.parameters_changed.emit(values)
        else:
            # When manual mode is disabled, emit empty dict or don't emit at all
            self.parameters_changed.emit({})

    # ------------------------------------------------------------------
    # Controller-facing helpers
    # ------------------------------------------------------------------
    def display_microscopy_path(self, path: Path | None) -> None:
        """Show the selected microscopy file."""
        if path:
            self._microscopy_path_field.setText(path.name)
        else:
            self._microscopy_path_field.setText("No microscopy file selected")

    def display_output_directory(self, path: Path | None) -> None:
        """Show the chosen output directory."""
        self._output_dir_field.setText(str(path or ""))

    def set_channel_options(
        self,
        phase_channels: Sequence[tuple[str, int | None]],
        fluorescence_channels: Sequence[tuple[str, int]],
    ) -> None:
        """Populate channel selectors with metadata-driven entries."""
        self._pc_combo.blockSignals(True)
        self._pc_combo.clear()
        for label, value in phase_channels:
            self._pc_combo.addItem(label, value)
        self._pc_combo.blockSignals(False)

        self._fl_list.blockSignals(True)
        self._fl_list.clear()
        for label, value in fluorescence_channels:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, value)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self._fl_list.addItem(item)
        self._fl_list.blockSignals(False)

    def apply_selected_channels(
        self, *, phase: int | None, fluorescence: Iterable[int]
    ) -> None:
        """Synchronise channel selections without emitting change events."""
        self._pc_combo.blockSignals(True)
        try:
            if phase is None:
                self._pc_combo.setCurrentIndex(0)
            else:
                index = self._pc_combo.findData(phase)
                if index != -1:
                    self._pc_combo.setCurrentIndex(index)
        finally:
            self._pc_combo.blockSignals(False)

        self._fl_list.blockSignals(True)
        try:
            self._fl_list.clearSelection()
            selected = set(fluorescence)
            for row in range(self._fl_list.count()):
                item = self._fl_list.item(row)
                value = item.data(Qt.ItemDataRole.UserRole)
                item.setSelected(value in selected)
        finally:
            self._fl_list.blockSignals(False)

    def set_processing_active(self, active: bool) -> None:
        """Toggle progress bar visibility based on processing state."""
        if active:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)
            self._progress_bar.setRange(0, 1)

    def set_process_enabled(self, enabled: bool) -> None:
        """Enable or disable the workflow start button."""
        self._process_button.setEnabled(enabled)

    def set_parameter_defaults(self, defaults: pd.DataFrame) -> None:
        """Replace the parameter table with controller-provided defaults."""
        self._param_panel.set_parameters_df(defaults)

    def set_parameter_value(self, name: str, value) -> None:
        """Update a single parameter value."""
        self._param_panel.set_parameter(name, value)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _initialize_parameter_defaults(self) -> None:
        defaults_data = {
            "fov_start": {"value": -1},
            "fov_end": {"value": -1},
            "batch_size": {"value": 2},
            "n_workers": {"value": 2},
        }
        df = pd.DataFrame.from_dict(defaults_data, orient="index")
        self._param_panel.set_parameters_df(df)
