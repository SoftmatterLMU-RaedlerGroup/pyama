from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QPushButton, QLabel, QComboBox, QListWidget, 
                             QListWidgetItem, QFileDialog, QMessageBox,
                             QProgressBar, QFrame)
from PySide6.QtCore import Qt, Signal, QThread
from typing_extensions import TypedDict
from pathlib import Path


class ND2Metadata(TypedDict, total=False):
    """Type definition for ND2 metadata structure"""
    # File info
    filepath: str
    filename: str
    
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
    log_message = Signal(str)  # Signal for logging messages
    
    def __init__(self):
        super().__init__()
        self.current_data = None
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
        self.nd2_button.clicked.connect(self.fake_load_data)  # Connected to fake method
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
        
        
    def select_nd2_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select ND2 File", "", "ND2 Files (*.nd2);;All Files (*)")
        
        if filepath:
            self.load_nd2_metadata(filepath)
            
            
    def load_nd2_metadata(self, filepath):
        self.nd2_label.setText(f"Loading: {Path(filepath).name}")
        self.nd2_button.setEnabled(False)
        
        # Start loading thread
        self.loader_thread = ND2LoaderThread(filepath)
        self.loader_thread.finished.connect(self.on_nd2_loaded)
        self.loader_thread.error.connect(self.on_load_error)
        self.loader_thread.start()
        
    def fake_load_data(self):
        """Fake data loading for UI testing"""
        from PySide6.QtCore import QTimer
        
        # Simulate loading state
        self.nd2_label.setText("Loading: test_data.nd2")
        self.nd2_button.setEnabled(False)
        
        # Simulate loading delay then complete
        QTimer.singleShot(1000, self.complete_fake_load)
        
    def complete_fake_load(self):
        """Complete fake data loading"""
        # Create fake metadata
        fake_metadata = {
            'filepath': '/fake/path/test_data.nd2',
            'filename': 'test_data.nd2',
            'channels': ['Phase Contrast', 'GFP', 'mCherry'],
            'sizes': {'c': 3, 't': 10, 'v': 2, 'x': 1024, 'y': 1024, 'z': 1},
            'n_channels': 3,
            'n_frames': 10,
            'n_fov': 2,
            'n_z_levels': 1,
            'height': 1024,
            'width': 1024,
            'pixel_microns': 0.1625,
            'date': None,
            'experiment': {},
            'fields_of_view': [0, 1],
            'frames': list(range(10)),
            'num_frames': 10,
            'total_images_per_channel': 20,
            'z_levels': [0]
        }
        
        # Update UI directly
        self.current_data = fake_metadata
        self.nd2_label.setText(fake_metadata['filename'])
        self.nd2_button.setEnabled(True)
        
        # Populate channels and enable UI
        self.populate_channels(fake_metadata)
        self.channel_group.setEnabled(True)
        self.load_button.setEnabled(True)
        
        # Auto-select some channels for convenience
        self.pc_combo.setCurrentIndex(1)  # Phase Contrast
        self.fl_combo.setCurrentIndex(2)  # GFP
        
        # Log the metadata information
        self.log_message.emit("📁 Fake ND2 file loaded successfully")
        self.log_message.emit(f"📊 Metadata Summary:")
        self.log_message.emit(f"  • Filename: {fake_metadata['filename']}")
        self.log_message.emit(f"  • Dimensions: {fake_metadata['width']}x{fake_metadata['height']} pixels")
        self.log_message.emit(f"  • Channels: {fake_metadata['n_channels']} ({', '.join(fake_metadata['channels'])})")
        self.log_message.emit(f"  • Time frames: {fake_metadata['n_frames']}")
        self.log_message.emit(f"  • Fields of view: {fake_metadata['n_fov']}")
        self.log_message.emit(f"  • Z levels: {fake_metadata['n_z_levels']}")
        self.log_message.emit(f"  • Pixel size: {fake_metadata['pixel_microns']:.4f} µm/pixel")
        self.log_message.emit("✅ Ready for channel assignment")
        
        self.status_message.emit(f"Fake data loaded. {fake_metadata['n_channels']} channels available.")
        
    def on_nd2_loaded(self, metadata):
        self.current_data = metadata
        
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
        
        QMessageBox.critical(self, "Loading Error", f"Failed to load ND2 file:\\n{error_msg}")
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
            
        self.load_button.setEnabled(True)
        
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
            'pc_channel': pc_channel_idx,
            'fl_channel': fl_channel_idx,
            'pc_channel_name': pc_channel_name,
            'fl_channel_name': fl_channel_name,
            'metadata': self.current_data
        }
        
        # Log channel assignment
        pc_name = pc_channel_name if pc_channel_name else "None"
        fl_name = fl_channel_name if fl_channel_name else "None"
        self.log_message.emit("🔗 Channel assignment completed:")
        self.log_message.emit(f"  • Phase Contrast: {pc_name}")
        self.log_message.emit(f"  • Fluorescence: {fl_name}")
        self.log_message.emit("🚀 Data ready for processing workflow")
        
        self.data_loaded.emit(data_info)
        self.status_message.emit("Data loaded and ready for processing")