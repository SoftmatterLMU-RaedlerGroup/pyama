"""
File loader widget for PyAMA-Qt processing application.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QListWidget,
)
from PySide6.QtCore import Signal, QThread
import logging
from pyama_core.io import load_nd2
from dataclasses import asdict
from pprint import pformat

logger = logging.getLogger(__name__)


class ND2LoaderThread(QThread):
    """Background thread for loading ND2 files."""

    finished = Signal(object)  # ND2Metadata object
    error = Signal(str)

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            # Pass a Path to the core loader
            nd2_path = Path(self.filepath)
            _, metadata = load_nd2(nd2_path)
            self.finished.emit(metadata)
        except Exception as e:
            self.error.emit(str(e))


class FileLoader(QWidget):
    """Widget for loading and selecting channels from ND2 files."""

    # Emits a tuple: (ND2Metadata, context)
    data_loaded = Signal(object)

    def __init__(self):
        super().__init__()
        self.metadata = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)

        # File selection group
        input_group = QGroupBox("Input")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(8)
        input_layout.setContentsMargins(10, 10, 10, 10)

        # ND2 file selection
        nd2_header_layout = QHBoxLayout()
        nd2_label = QLabel("ND2 File:")
        self.nd2_button = QPushButton("Browse...")
        self.nd2_button.clicked.connect(self.select_nd2_file)

        nd2_header_layout.addWidget(nd2_label)
        nd2_header_layout.addStretch()
        nd2_header_layout.addWidget(self.nd2_button)

        self.nd2_file = QLineEdit("")
        self.nd2_file.setReadOnly(True)

        input_layout.addLayout(nd2_header_layout)
        input_layout.addWidget(self.nd2_file)

        layout.addWidget(input_group)

        # Channel assignment group
        self.channel_group = QGroupBox("Channel Assignment")
        self.channel_group.setEnabled(False)
        channel_layout = QVBoxLayout(self.channel_group)
        channel_layout.setSpacing(8)
        channel_layout.setContentsMargins(10, 10, 10, 10)

        # Phase contrast assignment
        pc_layout = QHBoxLayout()
        pc_layout.addWidget(QLabel("Phase Contrast:"), 1)
        self.pc_combo = QComboBox()
        self.pc_combo.addItem("None", None)
        pc_layout.addWidget(self.pc_combo, 1)
        channel_layout.addLayout(pc_layout)

        # Fluorescence assignment (multi-select)
        fl_layout = QHBoxLayout()
        fl_layout.addWidget(QLabel("Fluorescence (multi-select):"), 1)
        self.fl_list = QListWidget()
        # Enable extended selection for multi-select
        try:
            from PySide6.QtWidgets import QAbstractItemView

            self.fl_list.setSelectionMode(QAbstractItemView.MultiSelection)
        except Exception:
            pass
        fl_layout.addWidget(self.fl_list, 1)
        channel_layout.addLayout(fl_layout)

        # Load confirmation
        self.load_button = QPushButton("Load Data")
        self.load_button.setEnabled(False)
        self.load_button.clicked.connect(self.load_data)
        channel_layout.addWidget(self.load_button)

        layout.addWidget(self.channel_group)

        # Add stretch to push everything to top
        layout.addStretch()

        # Connect signals

    def select_nd2_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select ND2 File", "", "ND2 Files (*.nd2);;All Files (*)"
        )

        if filepath:
            self.load_nd2_metadata(filepath)

    def load_nd2_metadata(self, filepath):
        self.nd2_file.setText(f"Loading: {Path(filepath).name}")
        self.nd2_button.setEnabled(False)
        logger.info(f"Loading ND2 file: {filepath}")

        # Start loading thread
        self.loader_thread = ND2LoaderThread(filepath)
        self.loader_thread.finished.connect(self.on_nd2_loaded)
        self.loader_thread.error.connect(self.on_load_error)
        self.loader_thread.start()

    def on_nd2_loaded(self, metadata):
        self.metadata = metadata

        # Pretty-print ND2Metadata as a dict
        try:
            md_dict = asdict(metadata)
        except Exception:
            # Fallback if not a dataclass instance
            md_dict = {
                "nd2_path": str(getattr(metadata, "nd2_path", "")),
                "base_name": getattr(metadata, "base_name", ""),
                "height": int(getattr(metadata, "height", 0)),
                "width": int(getattr(metadata, "width", 0)),
                "n_frames": int(getattr(metadata, "n_frames", 0)),
                "n_fovs": int(getattr(metadata, "n_fovs", 0)),
                "n_channels": int(getattr(metadata, "n_channels", 0)),
                "timepoints": list(getattr(metadata, "timepoints", [])),
                "channel_names": list(getattr(metadata, "channel_names", [])),
                "dtype": str(getattr(metadata, "dtype", "")),
            }
        logger.info("ND2 file loaded successfully:\n" + pformat(md_dict))

        # Update UI
        self.nd2_file.setText(metadata.base_name)
        self.nd2_button.setEnabled(True)

        # Populate channel list and dropdowns
        self.populate_channels(metadata)

        # Enable channel assignment
        self.channel_group.setEnabled(True)

    def on_load_error(self, error_msg):
        self.nd2_button.setEnabled(True)
        self.nd2_file.setText("No ND2 file selected")

        logger.error(f"Failed to load ND2 file: {error_msg}")
        QMessageBox.critical(
            self, "Loading Error", f"Failed to load ND2 file:\n{error_msg}"
        )

    def populate_channels(self, metadata):
        # Clear existing items
        self.pc_combo.clear()
        self.fl_list.clear()

        # Add default "None" option for PC
        self.pc_combo.addItem("None", None)

        # Add channels to dropdowns/lists
        for i, channel in enumerate(metadata.channel_names):
            # Store the channel index as the item data for easy retrieval
            self.pc_combo.addItem(f"Channel {i}: {channel}", channel)
            self.fl_list.addItem(f"Channel {i}: {channel}")

        # Don't auto-detect channels - let user choose manually
        # self.auto_detect_channels(metadata)

        self.load_button.setEnabled(True)

    def auto_detect_channels(self, metadata):
        """Auto-detect and assign channels based on names - DISABLED"""
        # Auto-detection is now disabled to require manual channel selection
        pass

    def load_data(self):
        if not self.metadata:
            return

        # Get selected channels (channel names)
        pc_channel_name = self.pc_combo.currentData()
        # Collect selected fluorescence channels (names and indices)
        selected_fl_items = self.fl_list.selectedItems()
        fl_channel_names = []
        fl_channel_indices = []
        if selected_fl_items:
            # Names are derived from the metadata list matching item text suffix
            channels = list(self.metadata.channel_names)  # ensure list
            for item in selected_fl_items:
                text = item.text()
                # Expect format "Channel {i}: {name}"; parse index
                try:
                    prefix, name = text.split(": ", 1)
                    idx = int(prefix.replace("Channel ", "").strip())
                except Exception:
                    # Fallback: try direct lookup by name
                    name = text
                    idx = channels.index(name) if name in channels else None
                if idx is not None:
                    fl_channel_indices.append(idx)
                    fl_channel_names.append(
                        channels[idx] if idx < len(channels) else name
                    )

        if pc_channel_name is None and not fl_channel_indices:
            QMessageBox.warning(self, "Warning", "Please select at least one channel")
            return

        # Convert PC channel name to index for processing
        pc_channel_idx = None
        if pc_channel_name is not None:
            if pc_channel_name in self.metadata.channel_names:
                pc_channel_idx = self.metadata.channel_names.index(pc_channel_name)

        # Build minimal context; output_dir is set later in workflow UI
        context = {
            "output_dir": None,
            "channels": {
                "pc": int(pc_channel_idx) if pc_channel_idx is not None else 0,
                "fl": list(fl_channel_indices),
            },
            "npy_paths": {},
            "params": {},
        }

        # Log channel assignment
        pc_name = pc_channel_name if pc_channel_name else "None"
        fl_names = ", ".join(fl_channel_names) if fl_channel_names else "None"
        logger.info("Channel assignment completed:")
        logger.info(f"  - Phase Contrast: {pc_name} (index: {pc_channel_idx})")
        logger.info(f"  - Fluorescence: {fl_names} (indices: {fl_channel_indices})")
        logger.info("Data ready for processing workflow")

        # Emit tuple: (ND2Metadata, context)
        self.data_loaded.emit((self.metadata, context))
