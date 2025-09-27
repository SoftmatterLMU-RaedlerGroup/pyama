"""Input/configuration panel for the processing workflow."""

from __future__ import annotations

import logging
from pathlib import Path

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

from pyama_qt.components import ParameterPanel
from pyama_qt.config import DEFAULT_DIR
from pyama_qt.ui import ModelBoundPanel
from ..models import ProcessingConfigModel, WorkflowStatusModel, ChannelSelection

logger = logging.getLogger(__name__)


class ProcessingConfigPanel(ModelBoundPanel):
    """Collects user inputs for running the processing workflow."""

    file_selected = Signal(Path)
    output_dir_selected = Signal(Path)
    channels_changed = Signal(object)  # ChannelSelection
    parameters_changed = Signal(dict)  # raw values
    process_requested = Signal()

    def build(self) -> None:
        layout = QHBoxLayout(self)

        self._input_group = self._build_input_group()
        self._output_group = self._build_output_group()

        layout.addWidget(self._input_group, 1)
        layout.addWidget(self._output_group, 1)

        # Channel UI will be interactive when metadata arrives; don't forcibly
        # toggle enabled/disabled here to keep logic simpler and more predictable.
        self._progress_bar.setVisible(False)

    def bind(self) -> None:
        self._nd2_button.clicked.connect(self._on_microscopy_clicked)
        self._output_button.clicked.connect(self._on_output_clicked)
        self._process_button.clicked.connect(self.process_requested.emit)
        self._pc_combo.currentIndexChanged.connect(self._emit_channel_selection)
        # Connect both signals for better click handling
        self._fl_list.itemClicked.connect(self._on_fl_item_clicked)
        self._fl_list.itemSelectionChanged.connect(self._emit_channel_selection)
        self._param_panel.parameters_changed.connect(self._on_parameters_changed)

    def set_models(
        self,
        config_model: ProcessingConfigModel,
        status_model: WorkflowStatusModel,
    ) -> None:
        self._config_model = config_model
        self._status_model = status_model
        config_model.microscopyPathChanged.connect(self._on_microscopy_path_changed)
        config_model.outputDirChanged.connect(self._on_output_dir_changed)
        config_model.metadataChanged.connect(self._on_metadata_changed)
        config_model.phaseChanged.connect(self._on_phase_changed)
        config_model.fluorescenceChanged.connect(self._on_fluorescence_changed)
        config_model.fovStartChanged.connect(self._on_fov_start_changed)
        config_model.fovEndChanged.connect(self._on_fov_end_changed)
        config_model.batchSizeChanged.connect(self._on_batch_size_changed)
        config_model.nWorkersChanged.connect(self._on_n_workers_changed)
        status_model.isProcessingChanged.connect(self._on_processing_changed)

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
        self.channels_changed.emit(
            ChannelSelection(phase=phase, fluorescence=fluorescence)
        )

    def _on_parameters_changed(self) -> None:
        values = self._param_panel.get_values()  # Assume returns dict
        self.parameters_changed.emit(values)  # Emit dict

    # ------------------------------------------------------------------
    # Model synchronisation
    # ------------------------------------------------------------------
    def _on_microscopy_path_changed(self, path: Path | None) -> None:
        if path:
            self._microscopy_path_field.setText(path.name)
        else:
            self._microscopy_path_field.setText("No microscopy file selected")

    def _on_output_dir_changed(self, path: Path | None) -> None:
        self._output_dir_field.setText(str(path or ""))

    def _on_metadata_changed(self, metadata) -> None:
        self._sync_channels()

    def _on_processing_changed(self, is_processing: bool) -> None:
        if is_processing:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)
            self._progress_bar.setRange(0, 1)

    def _on_phase_changed(self, phase: int | None) -> None:
        if self._config_model:
            self._pc_combo.blockSignals(True)
            try:
                self._pc_combo.setCurrentText(str(phase) if phase is not None else "")
            finally:
                self._pc_combo.blockSignals(False)

    def _on_fluorescence_changed(self, fluorescence: list | None) -> None:
        if self._config_model:
            self._fl_list.blockSignals(True)
            try:
                self._fl_list.clearSelection()
                if fluorescence:
                    for i in fluorescence:
                        item = self._fl_list.item(i)
                        if item:
                            item.setSelected(True)
            finally:
                self._fl_list.blockSignals(False)

    def _on_fov_start_changed(self, fov_start: int) -> None:
        if self._config_model:
            self._param_panel.set_parameter("fov_start", fov_start)

    def _on_fov_end_changed(self, fov_end: int) -> None:
        if self._config_model:
            self._param_panel.set_parameter("fov_end", fov_end)

    def _on_batch_size_changed(self, batch_size: int) -> None:
        if self._config_model:
            self._param_panel.set_parameter("batch_size", batch_size)

    def _on_n_workers_changed(self, n_workers: int) -> None:
        if self._config_model:
            self._param_panel.set_parameter("n_workers", n_workers)

    def _sync_channels(self) -> None:
        metadata = self._config_model.metadata() if self._config_model else None

        self._pc_combo.blockSignals(True)
        self._pc_combo.clear()
        self._pc_combo.addItem("None", None)

        self._fl_list.blockSignals(True)
        self._fl_list.clear()

        if metadata is not None:
            for idx, channel in enumerate(getattr(metadata, "channel_names", []) or []):
                label = f"Channel {idx}: {channel}"
                self._pc_combo.addItem(label, idx)
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, idx)
                # Set proper flags for selection
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self._fl_list.addItem(item)
                # Set selection state after adding to list
                channels = self._config_model.channels()
                if idx in channels.fluorescence:
                    item.setSelected(True)

            if self._config_model and self._config_model.channels().phase is not None:
                channels = self._config_model.channels()
                combo_index = self._pc_combo.findData(channels.phase)
                if combo_index != -1:
                    self._pc_combo.setCurrentIndex(combo_index)
        else:
            self._pc_combo.setCurrentIndex(0)

        self._pc_combo.blockSignals(False)
        self._fl_list.blockSignals(False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _initialize_parameter_defaults(self) -> None:
        defaults = {
            "fov_start": -1,
            "fov_end": -1,
            "batch_size": 2,
            "n_workers": 2,
        }
        self._param_panel.set_parameters(defaults)

    def show_error(self, message: str) -> None:
        """Display error message to user."""
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(self, "Error", message)

    def show_info(self, message: str) -> None:
        """Display info message to user."""
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "Information", message)
