from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox)
from PySide6.QtCore import Signal, QThread
from typing_extensions import TypedDict
from pathlib import Path

from ...logging_config import get_logger


class ND2Metadata(TypedDict, total=False):
    """Type definition for ND2 metadata structure"""
    # File info
    filepath: str
    filename: str
    native_dtype: str
    
    # From images.metadata
    channels: list[str]
    date: object  # datetime.datetime
    experiment: dict[str, object]
    fields_of_view: list[int]
    frames: list[int]
    height: int
    num_frames: int
    pixel_microns: float
    total_images_per_channel: int
    width: int
    z_levels: list[int]
    
    # From images.sizes
    sizes: dict[str, int]  # {'c': 2, 't': 1, 'v': 2, 'x': 2368, 'y': 1895, 'z': 3}
    
    # Derived properties
    n_channels: int
    n_frames: int
    n_fov: int
    n_z_levels: int


class ND2LoaderThread(QThread):
    """Background thread for loading ND2 files"""
    finished = Signal(dict)  # Will contain ND2Metadata
    error = Signal(str)
    
    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath
        
    def run(self):
        try:
            from nd2reader import ND2Reader
            
            with ND2Reader(self.filepath) as images:
                # Extract all metadata from images.metadata
                img_metadata = images.metadata or {}
                
                # Create comprehensive metadata dictionary
                metadata: ND2Metadata = {
                    # File info
                    'filepath': self.filepath,
                    'filename': Path(self.filepath).name,
                    
                    # From images.sizes (complete dictionary)
                    'sizes': dict(images.sizes),
                    
                    # From images.metadata (all available fields)
                    'channels': list(img_metadata.get('channels', [])),
                    'native_dtype': str(images.pixel_type),
                    'date': img_metadata.get('date'),
                    'experiment': img_metadata.get('experiment', {}),
                    'fields_of_view': img_metadata.get('fields_of_view', []),
                    'frames': img_metadata.get('frames', []),
                    'height': img_metadata.get('height', images.sizes.get('y', 0)),
                    'num_frames': img_metadata.get('num_frames', 0),
                    'pixel_microns': img_metadata.get('pixel_microns', 0.0),
                    'total_images_per_channel': img_metadata.get('total_images_per_channel', 0),
                    'width': img_metadata.get('width', images.sizes.get('x', 0)),
                    'z_levels': img_metadata.get('z_levels', []),
                    
                    # Derived properties for convenience
                    'n_channels': images.sizes.get('c', 1),
                    'n_frames': images.sizes.get('t', 1),
                    'n_fov': images.sizes.get('v', len(img_metadata.get('fields_of_view', [0]))),
                    'n_z_levels': images.sizes.get('z', len(img_metadata.get('z_levels', [0]))),
                }
                
            self.finished.emit(dict(metadata))
            
        except Exception as e:
            self.error.emit(str(e))


class FileLoader(QWidget):
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
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(8)
        file_layout.setContentsMargins(10, 10, 10, 10)
        
        # ND2 file selection
        self.nd2_label = QLabel("No ND2 file selected")
        self.nd2_label.setStyleSheet("QLabel { border: 1px solid gray; padding: 5px; }")
        file_layout.addWidget(self.nd2_label)
        
        self.nd2_button = QPushButton("Select ND2 File")
        self.nd2_button.clicked.connect(self.select_nd2_file)
        file_layout.addWidget(self.nd2_button)
        
        layout.addWidget(file_group)
        
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
            self, "Select ND2 File", "", "ND2 Files (*.nd2);;All Files (*)")
        
        if filepath:
            self.load_nd2_metadata(filepath)
            
    def load_nd2_metadata(self, filepath):
        self.nd2_label.setText(f"Loading: {Path(filepath).name}")
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
        self.logger.info(f"  - Dimensions: {metadata['width']}x{metadata['height']} pixels")
        self.logger.info(f"  - Channels: {metadata['n_channels']} ({', '.join(metadata['channels'])})")
        self.logger.info(f"  - Native dtype: {metadata['native_dtype']}")
        self.logger.info(f"  - FOVs: {metadata['n_fov']}")
        self.logger.info(f"  - Frames: {metadata['n_frames']}")
        self.logger.info(f"  - Pixel size: {metadata['pixel_microns']:.3f} µm")
        
        # Update UI
        self.nd2_label.setText(metadata['filename'])
        self.nd2_button.setEnabled(True)
        
        # Populate channel list and dropdowns
        self.populate_channels(metadata)
        
        # Enable channel assignment
        self.channel_group.setEnabled(True)
        self.status_message.emit(f"File loaded. {metadata['n_channels']} channels available.")
        
    def on_load_error(self, error_msg):
        self.nd2_button.setEnabled(True)
        self.nd2_label.setText("No ND2 file selected")
        
        self.logger.error(f"Failed to load ND2 file: {error_msg}")
        QMessageBox.critical(self, "Loading Error", f"Failed to load ND2 file:\n{error_msg}")
        self.status_message.emit("Error loading file")
        
    def populate_channels(self, metadata):
        # Clear existing items
        self.pc_combo.clear()
        self.fl_combo.clear()
        
        # Add default "None" options
        self.pc_combo.addItem("None", None)
        self.fl_combo.addItem("None", None)
        
        # Add channels to dropdowns
        for i, channel in enumerate(metadata['channels']):
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
            pc_channel_idx = self.current_data['channels'].index(pc_channel_name)
        if fl_channel_name is not None:
            fl_channel_idx = self.current_data['channels'].index(fl_channel_name)
            
        # Prepare data info for processing tabs
        data_info = {
            'type': 'nd2',
            'filepath': self.current_data['filepath'],
            'filename': self.current_data['filename'],
            'sizes': self.current_data['sizes'],
            'channels': self.current_data['channels'],
            'native_dtype': self.current_data.get('native_dtype'),
            'n_fov': self.current_data.get('n_fov', 0),
            'pc_channel': pc_channel_idx,
            'fl_channel': fl_channel_idx,
            'pc_channel_name': pc_channel_name,
            'fl_channel_name': fl_channel_name,
            'metadata': self.current_data
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