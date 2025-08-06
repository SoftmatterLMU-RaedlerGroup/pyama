from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QLineEdit, 
                             QFileDialog)
from PySide6.QtCore import Signal
import logging

from ...logging_config import get_logger


class Workflow(QWidget):
    process_requested = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.data_info = None
        self.logger = get_logger(__name__)
        self.setup_ui()
        
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Output section
        self.setup_output_section(layout)
        
        # Processing section
        self.setup_processing_section(layout)
        
        # Stretch to push everything to top
        layout.addStretch()
        
        
        
        
    def setup_output_section(self, layout):
        """Set up output settings section"""
        output_group = QGroupBox("Output Settings")
        output_layout = QVBoxLayout(output_group)
        
        # Base output directory
        dir_layout = QHBoxLayout()
        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("Select output directory...")
        self.output_dir_button = QPushButton("Browse...")
        self.output_dir_button.clicked.connect(self.select_output_directory)
        
        dir_layout.addWidget(QLabel("Output Directory:"))
        dir_layout.addWidget(self.output_dir, 1)
        dir_layout.addWidget(self.output_dir_button)
        output_layout.addLayout(dir_layout)
        
        # File naming info
        naming_info = QLabel("Output files will use ND2 filename as base (e.g., filename_segmented.npz)")
        naming_info.setStyleSheet("QLabel { font-style: italic; color: gray; }")
        output_layout.addWidget(naming_info)
        
        layout.addWidget(output_group)
        
    def setup_processing_section(self, layout):
        """Set up processing controls section"""
        process_group = QGroupBox("Processing Control")
        process_layout = QVBoxLayout(process_group)
        
        # Process button
        self.process_button = QPushButton("Start Complete Workflow")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.start_processing)
        self.process_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        process_layout.addWidget(self.process_button)
        
        layout.addWidget(process_group)
        
        
        
            
    def set_data_available(self, available, data_info=None):
        """Called when data becomes available or unavailable"""
        self.data_info = data_info
        
        if available and data_info:
            # Enable processing if we have at least one channel
            pc_channel = data_info.get('pc_channel')
            fl_channel = data_info.get('fl_channel')
            can_process = pc_channel is not None or fl_channel is not None
            self.process_button.setEnabled(can_process)
            
        else:
            self.process_button.setEnabled(False)
            
    def select_output_directory(self):
        """Open directory dialog to select output directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", "")
        
        if directory:
            self.output_dir.setText(directory)
            self.logger.info(f"Output directory selected: {directory}")
            
            
    def start_processing(self):
        """Start the complete workflow processing"""
        if not self.data_info:
            return
            
        # Validate inputs
        output_dir = self.output_dir.text().strip()
        if not output_dir:
            self.logger.error("No output directory selected")
            return
            
        # Use ND2 filename as base name
        base_name = self.data_info['filename'].split('.')[0]
            
        # All steps are enabled by default
        enabled_steps = ['segmentation', 'background_correction', 'tracking', 'bounding_box']
            
        # Prepare processing parameters with default values
        params = {
            'data_info': self.data_info,
            'output_dir': output_dir,
            'base_name': base_name,
            'enabled_steps': enabled_steps,
            
            # Default parameters for all steps
            'mask_size': 3,
            'div_horiz': 7,
            'div_vert': 5,
            'use_memmap': True,
            'max_displacement': 20,
            'memory_frames': 3,
        }
        
        # Emit signal to start processing
        self.process_requested.emit(params)
        
        # Update UI for processing state
        self.process_button.setEnabled(False)
        self.logger.info("Starting complete workflow...")
        self.logger.info("Processing stages: Binarization → Background Correction → Trace Extraction")
        self.logger.info(f"Parameters: mask_size={params['mask_size']}, div_horiz={params['div_horiz']}, div_vert={params['div_vert']}")
        
        
    def update_progress(self, value, message=""):
        """Update status"""
        if message:
            self.logger.info(message)
            
            
    def processing_finished(self, success, message=""):
        """Called when processing is complete"""
        self.process_button.setEnabled(True)
        
        if success:
            self.logger.info("✓ Complete workflow finished successfully")
            if message:
                self.logger.info(message)
        else:
            self.logger.error(f"✗ Workflow failed: {message}")
            
    def processing_error(self, error_message):
        """Called when processing encounters an error"""
        self.processing_finished(False, error_message)
        
        
        
        
