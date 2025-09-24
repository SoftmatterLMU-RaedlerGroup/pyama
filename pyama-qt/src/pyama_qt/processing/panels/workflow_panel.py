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
from pyama_qt.processing.state import (
    ChannelSelection,
    ProcessingParameters,
    ProcessingState,
)
from pyama_qt.ui import BasePanel

logger = logging.getLogger(__name__)


class ProcessingConfigPanel(BasePanel[ProcessingState]):
    """Collects user inputs for running the processing workflow."""

    file_selected = Signal(Path)
    output_dir_selected = Signal(Path)
    channels_changed = Signal(object)  # ChannelSelection
    parameters_changed = Signal(object)  # ProcessingParameters
    process_requested = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def build(self) -> None:
        layout = QHBoxLayout(self)

        self._input_group = self._build_input_group()
        self._output_group = self._build_output_group()

        layout.addWidget(self._input_group, 1)
        layout.addWidget(self._output_group, 1)

        # Allow channel UI to be interactive; items will appear once metadata is loaded.
        # We'll only disable it while processing is running.
        self._channel_container.setEnabled(True)
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
        # Ensure widget is interactive
        self._fl_list.setEnabled(True)
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
        self._process_button.setEnabled(False)
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
            "",
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
            "",
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
        params = self._collect_parameters()
        self.parameters_changed.emit(params)

    # ------------------------------------------------------------------
    # State synchronisation
    # ------------------------------------------------------------------
    def update_view(self) -> None:
        state = self.get_state()
        if state is None:
            return

        self._microscopy_path_field.setText(self._describe_microscopy(state))
        self._output_dir_field.setText(str(state.output_dir or ""))

        self._sync_channels(state)
        self._sync_parameters(state.parameters)
        self._sync_processing_state(state)

    def _describe_microscopy(self, state: ProcessingState) -> str:
        if state.metadata is not None:
            return getattr(state.metadata, "base_name", "Microscopy file loaded")
        if state.microscopy_path is not None:
            return state.microscopy_path.name
        return "No microscopy file selected"

    def _sync_channels(self, state: ProcessingState) -> None:
        metadata = state.metadata
        # Enable channel selection whenever we are not actively processing,
        # regardless of whether metadata has been loaded yet. The lists
        # will be empty until metadata arrives.
        self._channel_container.setEnabled(not state.is_processing)

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
                if idx in state.channels.fluorescence:
                    item.setSelected(True)

            if state.channels.phase is not None:
                combo_index = self._pc_combo.findData(state.channels.phase)
                if combo_index != -1:
                    self._pc_combo.setCurrentIndex(combo_index)
        else:
            self._pc_combo.setCurrentIndex(0)

        self._pc_combo.blockSignals(False)
        self._fl_list.blockSignals(False)

    def _sync_parameters(self, params: ProcessingParameters) -> None:
        param_dict = {
            "fov_start": params.fov_start,
            "fov_end": params.fov_end,
            "batch_size": params.batch_size,
            "n_workers": params.n_workers,
        }

        self._param_panel.blockSignals(True)
        self._param_panel.set_parameters_df(self._parameters_to_dataframe(param_dict))
        self._param_panel.blockSignals(False)

    def _sync_processing_state(self, state: ProcessingState) -> None:
        self._process_button.setEnabled(
            state.metadata is not None and not state.is_processing
        )
        self._nd2_button.setEnabled(not state.is_processing)
        self._output_button.setEnabled(not state.is_processing)

        if state.is_processing:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setVisible(False)
            self._progress_bar.setRange(0, 1)

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
        self._param_panel.set_parameters_df(self._parameters_to_dataframe(defaults))

    def _parameters_to_dataframe(self, values: dict) -> "pd.DataFrame":  # type: ignore[name-defined]
        import pandas as pd

        df = pd.DataFrame(
            {"name": list(values.keys()), "value": list(values.values())}
        ).set_index("name")
        return df

    def _collect_parameters(self) -> ProcessingParameters:
        df = self._param_panel.get_values_df()
        if df is None or "value" not in df.columns:
            df = self._parameters_to_dataframe(
                {
                    "fov_start": -1,
                    "fov_end": -1,
                    "batch_size": 2,
                    "n_workers": 2,
                }
            )

        values = {
            "fov_start": int(df.loc["fov_start", "value"]),
            "fov_end": int(df.loc["fov_end", "value"]),
            "batch_size": int(df.loc["batch_size", "value"]),
            "n_workers": int(df.loc["n_workers", "value"]),
        }
        return ProcessingParameters(**values)
