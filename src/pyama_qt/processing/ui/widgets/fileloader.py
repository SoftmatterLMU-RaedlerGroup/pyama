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
)
from PySide6.QtCore import Signal, QThread

from pyama_qt.utils.logging_config import get_logger
from pyama_qt.utils.nd2_loader import load_nd2_metadata


class ND2LoaderThread(QThread):
    """Background thread for loading ND2 files."""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            metadata = load_nd2_metadata(self.filepath)
            self.finished.emit(metadata)
        except Exception as e:
            self.error.emit(str(e))


class FileLoader(QWidget):
    """Widget for loading and selecting channels from ND2 files."""

    data_loaded = Signal(dict)
    status_message = Signal(str)

    def __init__(self):
        super().__init__()
        self.current_data = None
        self.logger = get_logger(__name__)
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

        # Fluorescence assignment
        fl_layout = QHBoxLayout()
        fl_layout.addWidget(QLabel("Fluorescence:"), 1)
        self.fl_combo = QComboBox()
        self.fl_combo.addItem("None", None)
        fl_layout.addWidget(self.fl_combo, 1)
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
        self.logger.info(f"Loading ND2 file: {filepath}")

        # Start loading thread
        self.loader_thread = ND2LoaderThread(filepath)
        self.loader_thread.finished.connect(self.on_nd2_loaded)
        self.loader_thread.error.connect(self.on_load_error)
        self.loader_thread.start()

    def on_nd2_loaded(self, metadata):
        self.current_data = metadata

        # Log file metadata
        self.logger.info(f"ND2 file loaded successfully: {metadata['filename']}")
        self.logger.info(
            f"  - Dimensions: {metadata['width']}x{metadata['height']} pixels"
        )
        self.logger.info(
            f"  - Channels: {metadata['n_channels']} ({', '.join(metadata['channels'])})"
        )
        self.logger.info(f"  - Native dtype: {metadata['native_dtype']}")
        self.logger.info(f"  - FOVs: {metadata['n_fov']}")
        self.logger.info(f"  - Frames: {metadata['n_frames']}")
        self.logger.info(f"  - Pixel size: {metadata['pixel_microns']:.3f} µm")

        # Update UI
        self.nd2_file.setText(metadata["filename"])
        self.nd2_button.setEnabled(True)

        # Populate channel list and dropdowns
        self.populate_channels(metadata)

        # Enable channel assignment
        self.channel_group.setEnabled(True)
        self.status_message.emit(
            f"File loaded. {metadata['n_channels']} channels available."
        )

    def on_load_error(self, error_msg):
        self.nd2_button.setEnabled(True)
        self.nd2_file.setText("No ND2 file selected")

        self.logger.error(f"Failed to load ND2 file: {error_msg}")
        QMessageBox.critical(
            self, "Loading Error", f"Failed to load ND2 file:\n{error_msg}"
        )
        self.status_message.emit("Error loading file")

    def populate_channels(self, metadata):
        # Clear existing items
        self.pc_combo.clear()
        self.fl_combo.clear()

        # Add default "None" options
        self.pc_combo.addItem("None", None)
        self.fl_combo.addItem("None", None)

        # Add channels to dropdowns
        for i, channel in enumerate(metadata["channels"]):
            self.pc_combo.addItem(f"Channel {i}: {channel}", channel)
            self.fl_combo.addItem(f"Channel {i}: {channel}", channel)

        # Don't auto-detect channels - let user choose manually
        # self.auto_detect_channels(metadata)

        self.load_button.setEnabled(True)

    def auto_detect_channels(self, metadata):
        """Auto-detect and assign channels based on names - DISABLED"""
        # Auto-detection is now disabled to require manual channel selection
        pass

    def load_data(self):
        if not self.current_data:
            return

        # Get selected channels (channel names)
        pc_channel_name = self.pc_combo.currentData()
        fl_channel_name = self.fl_combo.currentData()

        if pc_channel_name is None and fl_channel_name is None:
            QMessageBox.warning(self, "Warning", "Please select at least one channel")
            return

        # Convert channel names to indices for processing
        pc_channel_idx = None
        fl_channel_idx = None

        if pc_channel_name is not None:
            pc_channel_idx = self.current_data["channels"].index(pc_channel_name)
        if fl_channel_name is not None:
            fl_channel_idx = self.current_data["channels"].index(fl_channel_name)

        # Prepare data info for processing tabs
        data_info = {
            "type": "nd2",
            "filepath": self.current_data["filepath"],
            "filename": self.current_data["filename"],
            "channels": self.current_data["channels"],
            "native_dtype": self.current_data.get("native_dtype"),
            "n_fov": self.current_data.get("n_fov", 0),
            "pc_channel": pc_channel_idx,
            "fl_channel": fl_channel_idx,
            "pc_channel_name": pc_channel_name,
            "fl_channel_name": fl_channel_name,
            "metadata": self.current_data,
        }

        # Log channel assignment
        pc_name = pc_channel_name if pc_channel_name else "None"
        fl_name = fl_channel_name if fl_channel_name else "None"
        self.logger.info("Channel assignment completed:")
        self.logger.info(f"  - Phase Contrast: {pc_name} (index: {pc_channel_idx})")
        self.logger.info(f"  - Fluorescence: {fl_name} (index: {fl_channel_idx})")
        self.logger.info("Data ready for processing workflow")

        self.data_loaded.emit(data_info)
        self.status_message.emit("Data loaded and ready for processing")
